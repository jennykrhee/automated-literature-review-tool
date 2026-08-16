#!/bin/sh
set -eu
cd "$(dirname "$0")"
. .venv/bin/activate
python -m src.radar --since 3 >> output/radar.log 2>&1
