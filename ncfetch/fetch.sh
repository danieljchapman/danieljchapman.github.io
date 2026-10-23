#!/usr/bin/env bash
# Downloads North Carolina source files that are not reachable from Claude's workspace.
set -u
cd "$(dirname "$0")"
mkdir -p out
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get() { curl -sS -L -m 300 -A "$UA" -o "out/$2" -w "$1 %{http_code} %{size_download}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
for d in 2016_11_08 2018_11_06 2020_11_03 2022_11_08 2024_11_05 2026_03_03; do
  get "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/$d/results_pct_${d//_/}.zip" "results_pct_${d//_/}.zip"
done
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ENRS/2026_11_03/" s3_2026_11_03.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ENRS/2026_03_03/" s3_2026_03_03.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ENRS/&delimiter=/" s3_enrs.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ShapeFiles/&delimiter=/" s3_shapefiles.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?delimiter=/" s3_root.xml
for p in Redistricting Redistricting/C2025E Redistricting/C2022C Redistricting/Archive; do
  get "https://www.ncleg.gov/$p" "ncleg_${p//\//_}.html"
done
ls -la out >> out/log.txt
