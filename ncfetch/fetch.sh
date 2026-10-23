#!/usr/bin/env bash
# Round 2: congressional plan shapefiles and NCSBE shape listings.
set -u
cd "$(dirname "$0")"
mkdir -p out
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get() { curl -sS -L -g -m 300 -A "$UA" -o "out/$2" -w "$1 %{http_code} %{size_download}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
N=https://www.ncleg.gov/Files/GIS/Plans_Main
get "$N/Congress_2016/shp.zip" c2016.zip
get "$N/Congress_2019/HB1029%203rd%20Edition%20-%20Shapefile.zip" c2019.zip
get "$N/Congress_2022_Court/2022%20Interim%20Congressional%20-%20Shapefile.zip" c2022.zip
get "$N/Congress_2023/SL%202023-145%20Congress%20-%20Shapefile.zip" c2023.zip
get "$N/Congress_2025/SL%202025-95%20Congress%20-%20Shapefile.zip" c2025.zip
get "https://www.ncleg.gov/Redistricting/C2025E/Plans" c2025e_plans.html
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ShapeFiles/USCongress/" s3_uscongress.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ShapeFiles/CountyBoundary/" s3_county.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/?prefix=ShapeFiles/LegislativeDistricts/" s3_leg.xml
get "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/layout_results_pct.txt" layout_results_pct.txt
get "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/ReadMe_PUBLIC_DATA.txt" readme.txt
get "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip" results_pct_20261103.zip
curl -sS -I -m 30 "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2026_11_03/results_pct_20261103.zip" > out/head_2026.txt 2>&1
ls -la out >> out/log.txt
