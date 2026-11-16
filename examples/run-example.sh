#!/bin/sh
# Run the checker over each example file and show the result.
# The flagged example fails on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/clean.svg examples/flagged.svg examples/edge.svg; do
  echo "== $f =="
  python3 src/svg_viewbox_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/svg_viewbox_checker.py examples/ || true
