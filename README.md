# svg-viewbox-checker-cli

Check every SVG file carries a `viewBox` on its root `<svg>` — fail CI when one does not.

[![CI](https://github.com/haiderstudio/svg-viewbox-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/svg-viewbox-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`svg_viewbox_checker` reads each SVG file, checks
the root `<svg>` element carries a `viewBox`
attribute, and reports each file missing it — or
carrying an empty one, which scales nothing either
— with the file and the line number. It exits 1
when any file is missing a usable viewBox, so it can
fail a CI run. A file whose root `<svg>` carries a
viewBox exits 0.

- An SVG with no viewBox does not scale — it renders
  at its fixed width and height and breaks responsive
  layouts, and the failure looks like a CSS bug, not
  a missing attribute. This names the exact file and
  line, and the fix is one attribute per file.
- Only the root `<svg>` is checked: a viewBox on a
  nested element does not make the file scale.
- The root element may use a namespace prefix or a
  default namespace — the check reads the local name,
  so `<svg:svg>` and `<svg>` count the same. A file
  that is not well-formed XML is reported, not
  passed: a viewBox cannot be trusted in a file that
  does not parse.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  files ending in `.svg` only, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are
  never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one SVG document read from standard input.

## Who it is for

Every site shipping SVG icons — a logo, a menu icon,
a button icon. One icon without a viewBox renders at
its fixed size while the rest scale, and the layout
breaks on one screen size only, so it looks like a
CSS bug and wastes an afternoon. This is the gate
that stops it at the pull request.

## What it does NOT do

- It does not check the `<title>` element inside an
  SVG — that is repo #92, svg-title-checker-cli.
  The viewBox attribute is a different check on the
  same files.
- It does not check that the viewBox values are
  sensible, or that the width and height match them.
  A viewBox with nonsense numbers is a different
  job — this tool only checks that the attribute is
  there and not empty.
- It does not check whether the SVG renders, or
  whether any element inside it is valid.
- It never rewrites a file, and it never touches the
  network.

## How this differs

- A fresh search of GitHub on Nov 15, 2026 found 0
  results for `"svg-viewbox-checker-cli"` and 0
  results for `svg viewbox checker` — a completely
  empty field.
- No rival checks viewBox attributes in local SVG
  files.

## Install

```sh
git clone https://github.com/haiderstudio/svg-viewbox-checker-cli.git
cd svg-viewbox-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one SVG file:

```sh
python3 src/svg_viewbox_checker.py icon.svg
```

A file whose root `<svg>` carries a viewBox passes:

```sh
$ python3 src/svg_viewbox_checker.py examples/clean.svg
OK — 1 file(s) checked, every SVG carries a viewBox.
```

A file missing a viewBox fails, with the file and
line:

```sh
$ python3 src/svg_viewbox_checker.py examples/flagged.svg
FAIL examples/flagged.svg: line 2 root <svg> has no viewBox attribute
Checked 1 file(s), 1 SVG file(s) without a viewBox in 1 file(s).
```

Check a whole folder (`.svg` files only):

```sh
$ python3 src/svg_viewbox_checker.py examples/
FAIL examples/flagged.svg: line 2 root <svg> has no viewBox attribute
Checked 3 file(s), 1 SVG file(s) without a viewBox in 1 file(s).
```

Check one document from standard input:

```sh
$ printf '<svg width="24" height="24"></svg>\n' | python3 src/svg_viewbox_checker.py --stdin
FAIL <stdin>: line 1 root <svg> has no viewBox attribute
Checked 1 file(s), 1 SVG file(s) without a viewBox in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/svg_viewbox_checker.py --json examples/flagged.svg
{
  "files": [
    {
      "path": "examples/flagged.svg",
      "findings": [
        {
          "line": 2,
          "reason": "root <svg> has no viewBox attribute"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 1
}
```

Exit codes: 0 when every SVG carries a viewBox, 1
when any file lacks one or a file cannot be read or
parsed, 2 for a usage error (a missing path, a bad
flag, or no SVG files found).

## Examples

A namespaced root, a comment before the root, and a
viewBox with negative values are all handled —
`examples/edge.svg` has all of them, and it passes:

```sh
$ python3 src/svg_viewbox_checker.py examples/edge.svg
OK — 1 file(s) checked, every SVG carries a viewBox.
```

An empty viewBox fails just like a missing one:

```sh
$ printf '<svg viewBox=""></svg>\n' | python3 src/svg_viewbox_checker.py --stdin
FAIL <stdin>: line 1 root <svg> has an empty viewBox attribute
Checked 1 file(s), 1 SVG file(s) without a viewBox in 1 file(s).
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_svg_viewbox_checker.py
```

The tests cover viewBox detection (an SVG with a
viewBox passes, one without fails with its line, an
empty viewBox fails, a whitespace-only viewBox
fails, a lowercase `viewbox` does not count, a
viewBox on a child element does not count, a root
that is not `<svg>` fails, a namespaced root passes
and fails the same way, a comment before the root
reports the root's own line, a doctype before the
root, a root tag split across lines reports the line
it starts on, negative and decimal viewBox values
pass, a self-closing root with and without a viewBox,
a nested `<svg>` without a viewBox ignored, malformed
XML is an error not a pass, an empty document is an
error, plain text is an error, mismatched tags are
an error, a byte-order mark before the root passes),
the CLI (exit 0/1/2, folder walking for several SVG
files, nested folders, `--no-recursive`, `--exclude`,
`.git` skipped, a direct file checked whatever its
name, duplicate paths checked once, `--json` output,
a malformed SVG file fails, `--stdin`, bad flags,
missing paths, empty folders, `--version`, input
files left unchanged, the tool run from another
folder and under a changed HOME), the bundled
examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs
checked against it), and hygiene checks (no
placeholder text, no absolute paths, no real secrets
outside the tests and examples, stdlib imports only,
no network use in the source, `.env` first in
`.gitignore`, CI file runs the test file, README
names the neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking viewBox attributes is not new, and
the parsing follows Python's own standard-library
XML parser — but no existing tool does this one job,
checking that every SVG file in local files carries
a viewBox on its root element, as a tested
command-line gate with a CI exit code, as the search
above shows — and every line of code here is
original, built on nothing but Python's standard
library.
