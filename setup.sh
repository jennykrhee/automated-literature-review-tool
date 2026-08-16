#!/bin/sh
set -eu
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Setup complete. Edit .env, then run: . .venv/bin/activate && python -m src.radar --since 7"
