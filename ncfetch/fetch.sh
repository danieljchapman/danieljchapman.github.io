#!/usr/bin/env bash
# Round 7: importer test with the official precinct counts (no publishing).
set -u
cd "$(dirname "$0")"
mkdir -p out
python3 nc/nc_live.py --date 2026-11-03 --out out >> out/log.txt 2>&1
python3 nc/nc_live.py --date 2024-11-05 --out out24 >> out/log.txt 2>&1
head -c 400 out/live_status.json >> out/log.txt; rm -rf out/live_2026.csv out24
