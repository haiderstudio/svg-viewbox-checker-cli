# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the SVG files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL.

It only checks that the root <svg> carries a viewBox. It never adds one, never edits a file, and never runs code found in an SVG file.

If you find a case where the tool rewrites a file, opens a URL, or reports a pass for an SVG file whose root <svg> has no viewBox, please open an issue describing the exact commands and input. Do not include any real secret in the report.
