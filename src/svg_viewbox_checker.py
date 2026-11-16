#!/usr/bin/env python3
"""Check every SVG file carries a viewBox on its root <svg>.

Run: python3 src/svg_viewbox_checker.py icon.svg
     python3 src/svg_viewbox_checker.py icons/
     python3 src/svg_viewbox_checker.py --stdin < icon.svg

An SVG with no viewBox does not scale — it renders
at its fixed width and height and breaks responsive
layouts, and the failure looks like a CSS bug, not a
missing attribute. This tool reads each SVG file,
checks the root <svg> element carries a viewBox
attribute, and reports each file missing it — or
carrying an empty one, which scales nothing either —
with the file and the line number. It exits 1 when
any file is missing a usable viewBox, so it can fail
a CI run. A file whose root <svg> carries a viewBox
exits 0.

A file given directly on the command line is always
checked, whatever its name. A folder is walked for
files ending in .svg only, recursively by default
(--no-recursive stops at the top level). .git
folders are never walked, and directory links are
never followed.

Only the root <svg> is checked: a viewBox on a
nested element does not make the file scale. The
root element may use a namespace prefix or a
default namespace — the check reads the local name,
so <svg:svg> and <svg> count the same. A file that
is not well-formed XML is reported, not passed: a
viewBox cannot be trusted in a file that does not
parse.

It never rewrites a file, never touches the network,
and reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
import xml.parsers.expat
from pathlib import Path

__version__ = "1.0.0"

SVG_SUFFIXES = (".svg",)


def _local_name(name):
    """The local part of an expat element name.

    With a namespace separator set, expat reports a
    namespaced name as "uri localname" — the part after
    the last space is the local name. A name with no
    namespace comes back unchanged.
    """
    return name.rsplit(" ", 1)[-1]


def check_bytes(data):
    """Check one document's bytes.

    Returns (findings, error): findings is a list of
    {"line": int, "reason": str} — at most one entry,
    for the root element — and error is None or a
    string saying why the file could not be checked
    at all.
    """
    findings = []
    state = {"root_seen": False}

    def start_element(name, attrs):
        if state["root_seen"]:
            return
        state["root_seen"] = True
        line = parser.CurrentLineNumber
        local = _local_name(name)
        if local != "svg":
            findings.append({
                "line": line,
                "reason": "root element is <%s>, not <svg>" % local,
            })
            return
        if "viewBox" not in attrs:
            findings.append({
                "line": line,
                "reason": "root <svg> has no viewBox attribute",
            })
        elif attrs["viewBox"].strip() == "":
            findings.append({
                "line": line,
                "reason": "root <svg> has an empty viewBox attribute",
            })

    parser = xml.parsers.expat.ParserCreate(namespace_separator=" ")
    parser.StartElementHandler = start_element
    try:
        parser.Parse(data, True)
    except xml.parsers.expat.ExpatError as exc:
        return [], "could not be parsed: %s" % exc
    if not state["root_seen"]:
        return [], "could not be parsed: no root element found"
    return findings, None


def check_text(text):
    """Check one document's text (convenience wrapper)."""
    return check_bytes(text.encode("utf-8"))


def check_file(path):
    """Check one file. Returns (findings, error)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return [], str(exc)
    return check_bytes(data)


def _is_svg_file(path):
    return Path(path).name.lower().endswith(SVG_SUFFIXES)


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of SVG files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .svg
    only. .git folders are never walked, and directory
    links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_svg_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one file without a viewBox."""
    return ("FAIL %s: line %d %s"
            % (path, finding["line"], finding["reason"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no SVG files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d SVG file(s) without a "
                  "viewBox in %d file(s)."
                  % (len(files), findings, files_with_findings))
        else:
            print("OK — %d file(s) checked, every SVG carries a "
                  "viewBox." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False):
    """Check one SVG document read from standard input."""
    data = sys.stdin.buffer.read()
    bad, error = check_bytes(data)
    findings = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": bad,
                        "error": error}],
             "checked": 1, "findings": findings},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for finding in bad:
            print(format_finding("<stdin>", finding))
        if findings:
            print("Checked 1 file(s), %d SVG file(s) without a "
                  "viewBox in 1 file(s)." % findings)
        else:
            print("OK — 1 file(s) checked, every SVG carries a "
                  "viewBox.")
    return 1 if findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="svg_viewbox_checker",
        description="Check every SVG file carries a viewBox on "
                    "its root <svg>, fail CI when one does not.")
    parser.add_argument("paths", nargs="*",
                        help="SVG files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one SVG document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one SVG file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
