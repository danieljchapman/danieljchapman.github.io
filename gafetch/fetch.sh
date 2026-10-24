#!/usr/bin/env bash
# run 2
pip install -q playwright pyshp && python -m playwright install --with-deps chromium >/dev/null 2>&1
python3 gafetch/probe2.py
