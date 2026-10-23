#!/usr/bin/env bash
# Round 5: run the NC importer against the live 2026 file from GitHub's servers (no publishing).
set -u
cd "$(dirname "$0")"
mkdir -p out
for i in 1 2 3; do
  ( time python3 nc/nc_live.py --date 2026-11-03 --out out ) >> out/log.txt 2>&1
  sleep 20
done
head -c 600 out/live_status.json >> out/log.txt
rm -f out/live_2026.csv
