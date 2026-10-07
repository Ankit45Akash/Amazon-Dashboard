#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
(sleep 2; command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5000 || open http://127.0.0.1:5000) 2>/dev/null &
python app.py
