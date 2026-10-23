#!/usr/bin/env bash
# Round 3: 2025 congressional plan, county boundaries, older general-election results (2002-2014).
set -u
cd "$(dirname "$0")"
mkdir -p out
get() { curl -sS -L -g -m 300 -o "out/$2" -w "$1 %{http_code} %{size_download}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
B=https://s3.amazonaws.com/dl.ncsbe.gov
get "$B/ShapeFiles/USCongress/SL%202025-95%20-%20Shapefile.zip" c2025.zip
get "$B/ShapeFiles/CountyBoundary/NC_State_County_Boundary_NCGS_2017.zip" counties.zip
for d in 2002_11_05 2004_11_02 2006_11_07 2008_11_04 2010_11_02 2012_11_06 2014_11_04; do
  get "$B/?prefix=ENRS/$d/" "s3_$d.xml"
done
ls -la out >> out/log.txt
