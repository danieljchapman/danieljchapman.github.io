#!/usr/bin/env bash
# Round 6: the election-night site's own data files (precincts reported).
set -u
cd "$(dirname "$0")"
mkdir -p out
get() { curl -sS -L -g -m 120 -o "out/$2" -w "$1 %{http_code} %{size_download} %{content_type}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
E=https://er.ncsbe.gov/enr
get "$E/elections.txt" elections.txt
for d in 20260303 20261103 20241105; do
  for f in county office contest results_0 results_1 results_60; do get "$E/$d/data/$f.txt" "${d}_$f.txt"; done
done
ls -la out >> out/log.txt
