#!/usr/bin/env python3
"""Tests for svg_viewbox_checker — stdlib unittest only.

Every SVG document in this file is made up for testing.
No real secret appears anywhere in this file.
"""

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import svg_viewbox_checker as checker

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src/svg_viewbox_checker.py"


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text):
    findings, error = checker.check_text(text)
    assert error is None, error
    return findings


def svg(viewbox='viewBox="0 0 24 24"', extra=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" %s %s>\n'
            '  <path d="M0 0h24v24H0z"/>\n'
            '</svg>\n' % (extra, viewbox))


class TestViewBoxDetection(unittest.TestCase):
    def test_svg_with_viewbox_passes(self):
        self.assertEqual(findings_of(svg()), [])

    def test_svg_without_viewbox_fails_with_line(self):
        bad = findings_of(svg(viewbox=""))
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)
        self.assertIn("no viewBox attribute", bad[0]["reason"])

    def test_empty_viewbox_fails(self):
        bad = findings_of(svg(viewbox='viewBox=""'))
        self.assertEqual(len(bad), 1)
        self.assertIn("empty viewBox", bad[0]["reason"])

    def test_whitespace_only_viewbox_fails(self):
        bad = findings_of(svg(viewbox='viewBox="   "'))
        self.assertEqual(len(bad), 1)
        self.assertIn("empty viewBox", bad[0]["reason"])

    def test_lowercase_viewbox_does_not_count(self):
        # XML attributes are case-sensitive: viewbox is not viewBox.
        bad = findings_of(svg(viewbox='viewbox="0 0 24 24"'))
        self.assertEqual(len(bad), 1)
        self.assertIn("no viewBox attribute", bad[0]["reason"])

    def test_viewbox_on_child_does_not_count(self):
        text = ('<svg xmlns="http://www.w3.org/2000/svg">\n'
                '  <g viewBox="0 0 24 24"></g>\n'
                '</svg>\n')
        bad = findings_of(text)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_root_not_svg_fails(self):
        bad = findings_of('<html><body></body></html>\n')
        self.assertEqual(len(bad), 1)
        self.assertIn("not <svg>", bad[0]["reason"])
        self.assertIn("html", bad[0]["reason"])

    def test_namespaced_root_passes(self):
        text = ('<svg:svg xmlns:svg="http://www.w3.org/2000/svg" '
                'viewBox="0 0 24 24">\n'
                '  <svg:circle cx="12" cy="12" r="10"/>\n'
                '</svg:svg>\n')
        self.assertEqual(findings_of(text), [])

    def test_namespaced_root_without_viewbox_fails(self):
        text = ('<svg:svg xmlns:svg="http://www.w3.org/2000/svg">\n'
                '</svg:svg>\n')
        bad = findings_of(text)
        self.assertEqual(len(bad), 1)
        self.assertIn("no viewBox attribute", bad[0]["reason"])

    def test_comment_before_root_reports_root_line(self):
        text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!-- A comment before the root element -->\n'
                '<svg xmlns="http://www.w3.org/2000/svg">\n'
                '</svg>\n')
        bad = findings_of(text)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)

    def test_doctype_before_root(self):
        text = ('<?xml version="1.0"?>\n'
                '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
                '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
                '<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 100 100"></svg>\n')
        self.assertEqual(findings_of(text), [])

    def test_multiline_root_tag_reports_start_line(self):
        text = ('<svg\n'
                '  xmlns="http://www.w3.org/2000/svg"\n'
                '  width="24"\n'
                '  height="24">\n'
                '</svg>\n')
        bad = findings_of(text)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_viewbox_with_negative_and_decimal_values(self):
        text = ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="-1.5 -2 26.5 26"></svg>\n')
        self.assertEqual(findings_of(text), [])

    def test_self_closing_svg_with_viewbox_passes(self):
        self.assertEqual(
            findings_of('<svg xmlns="http://www.w3.org/2000/svg" '
                        'viewBox="0 0 24 24"/>\n'), [])

    def test_self_closing_svg_without_viewbox_fails(self):
        bad = findings_of('<svg xmlns="http://www.w3.org/2000/svg"/>\n')
        self.assertEqual(len(bad), 1)

    def test_nested_svg_without_viewbox_ignored(self):
        # Only the root <svg> is checked.
        text = ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 24 24">\n'
                '  <svg width="12" height="12"></svg>\n'
                '</svg>\n')
        self.assertEqual(findings_of(text), [])

    def test_malformed_xml_is_an_error_not_a_pass(self):
        findings, error = checker.check_text(
            '<svg viewBox="0 0 24 24">\n')
        self.assertEqual(findings, [])
        self.assertIn("could not be parsed", error)

    def test_empty_document_is_an_error(self):
        findings, error = checker.check_text("")
        self.assertEqual(findings, [])
        self.assertIn("could not be parsed", error)

    def test_plain_text_is_an_error(self):
        findings, error = checker.check_text("hello, world\n")
        self.assertEqual(findings, [])
        self.assertIn("could not be parsed", error)

    def test_mismatched_tags_is_an_error(self):
        findings, error = checker.check_text(
            '<svg viewBox="0 0 24 24"></svgg>\n')
        self.assertEqual(findings, [])
        self.assertIn("could not be parsed", error)

    def test_bom_before_root_passes(self):
        data = (b'\xef\xbb\xbf<svg xmlns="http://www.w3.org/2000/svg" '
                b'viewBox="0 0 24 24"></svg>\n')
        findings, error = checker.check_bytes(data)
        self.assertIsNone(error)
        self.assertEqual(findings, [])


class TestCLI(unittest.TestCase):
    def test_clean_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg())
            code, out, err = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("every SVG carries a viewBox", out)
            self.assertEqual(err, "")

    def test_flagged_file_exit_1_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg(viewbox=""))
            code, out, err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("line 1", out)
            self.assertIn("no viewBox attribute", out)
            self.assertIn(path, out)

    def test_folder_walk_finds_svg_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.svg", svg())
            write(tmp, "b.svg", svg(viewbox=""))
            write(tmp, "notes.txt", svg(viewbox=""))
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s)", out)
            self.assertIn("b.svg", out)
            self.assertNotIn("notes.txt", out)

    def test_folder_walk_skips_nested_with_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.svg", svg())
            write(tmp, "sub/b.svg", svg(viewbox=""))
            code, out, err = run_cli([tmp, "--no-recursive"])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s)", out)

    def test_exclude_skips_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.svg", svg())
            write(tmp, "b.svg", svg(viewbox=""))
            code, out, err = run_cli([tmp, "--exclude", "b.svg"])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_git_folder_skipped_in_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.svg", svg())
            write(tmp, ".git/b.svg", svg(viewbox=""))
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "icon.txt", svg(viewbox=""))
            code, out, err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("icon.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg())
            code, out, err = run_cli([path, path])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg(viewbox=""))
            code, out, err = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(data["files"][0]["path"], path)
            self.assertEqual(
                data["files"][0]["findings"][0]["line"], 1)
            self.assertIn("no viewBox attribute",
                          data["files"][0]["findings"][0]["reason"])
            self.assertIsNone(data["files"][0]["error"])

    def test_malformed_svg_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", "<svg viewBox=\"0 0 1 1\">\n")
            code, out, err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("could not be parsed", out)

    def test_stdin_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SRC), "--stdin"],
                input=svg(), cwd=tmp,
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("every SVG carries a viewBox",
                          result.stdout)

    def test_stdin_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SRC), "--stdin"],
                input=svg(viewbox=""), cwd=tmp,
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAIL <stdin>: line 1 root <svg> has no "
                          "viewBox attribute", result.stdout)

    def test_stdin_with_paths_is_usage_error(self):
        code, out, err = run_cli(["--stdin", "a.svg"])
        self.assertEqual(code, 2)

    def test_no_paths_is_usage_error(self):
        code, out, err = run_cli([])
        self.assertEqual(code, 2)

    def test_missing_path_exit_2(self):
        code, out, err = run_cli(["/nonexistent/path/xyz"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no SVG files found", err)

    def test_bad_flag_exit_2(self):
        code, out, err = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, err = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("svg_viewbox_checker 1.0.0", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg(viewbox=""))
            before = Path(path).read_text()
            run_cli([path])
            self.assertEqual(Path(path).read_text(), before)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.svg", svg())
            result = subprocess.run(
                [sys.executable, str(SRC), "a.svg"],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("every SVG carries a viewBox",
                          result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.svg", svg())
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                code, out, err = run_cli([path])
            finally:
                if old_home is None:
                    del os.environ["HOME"]
                else:
                    os.environ["HOME"] = old_home
            self.assertEqual(code, 0)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        clean = subprocess.run(
            [sys.executable, "src/svg_viewbox_checker.py",
             "examples/clean.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0)
        self.assertIn(clean.stdout.strip(), readme)
        flagged = subprocess.run(
            [sys.executable, "src/svg_viewbox_checker.py",
             "examples/flagged.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(flagged.returncode, 1)
        self.assertIn(flagged.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/svg_viewbox_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 1 SVG file(s) without a "
                      "viewBox in 1 file(s).", folder.stdout)
        self.assertIn("Checked 3 file(s), 1 SVG file(s) without a "
                      "viewBox in 1 file(s).", readme)
        edge = subprocess.run(
            [sys.executable, "src/svg_viewbox_checker.py",
             "examples/edge.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        js = subprocess.run(
            [sys.executable, "src/svg_viewbox_checker.py",
             "--json", "examples/flagged.svg"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_real_secrets_outside_tests_and_examples(self):
        # The source holds no key values at all; the tests
        # and examples hold fake values only, so they are
        # excluded from this scan.
        patterns = [
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
            re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
            re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
            re.compile(r"AIza[0-9A-Za-z_-]{35}"),
            re.compile(r"[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"),
            re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
            re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ"),
        ]
        hits = []
        for path in self._repo_files():
            text = path.read_text(errors="ignore")
            for pattern in patterns:
                if pattern.search(text):
                    hits.append("%s: %s" % (path.name, pattern.pattern))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/svg_viewbox_checker.py",
                       REPO / "tests/test_svg_viewbox_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"svg_viewbox_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/svg_viewbox_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_svg_viewbox_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("svg-title-checker-cli", readme)


if __name__ == "__main__":
    unittest.main()
