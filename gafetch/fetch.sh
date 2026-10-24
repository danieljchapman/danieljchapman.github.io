#!/usr/bin/env bash
# run 1
pip install -q playwright pyshp && python -m playwright install --with-deps chromium >/dev/null 2>&1
python3 gafetch/probe.py census clarity enhanced
