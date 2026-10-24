#!/usr/bin/env bash
# NC legislative plan shapefiles (temporary branch; not part of the site).
set -u
cd "$(dirname "$0")"
mkdir -p out
get() { curl -sS -L -g -m 300 -o "out/$2" -w "$1 %{http_code} %{size_download}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
N=https://www.ncleg.gov/Files/GIS/Plans_Main
B=https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/LegislativeDistricts/Shapefiles
get "$N/House_2011/shp.zip" h2011.zip
get "$N/House_2017/2017%20House%20Redistricting%20Plan%20A2%20-%20Shapefile.zip" h2017.zip
get "$N/House_2018_Court/House%2018%20USSupCt%20-%20Shapefile.zip" h2018.zip
get "$N/House_2019/HB%201020%20H%20Red%20Comm%20CSBK-25_Shapefile.zip" h2019.zip
get "$B/House/2019_state_house_with_HB1017.zip" h2019w.zip
get "$N/House_2022/SL%202022-4%20House%20-%20Shapefile.zip" h2022.zip
get "$N/House_2023/SL%202023-149%20House%20-%20Shapefile.zip" h2023.zip
get "$N/Senate_2011/shp.zip" s2011.zip
get "$N/Senate_2017/2017%20Senate%20Floor%20Redistricting%20Plan%20%E2%80%93%204th%20Ed%20-%20Shapefile.zip" s2017.zip
get "$N/Senate_2018_Court/Senate%2018%20USSupCt%20-%20Shapefile.zip" s2018.zip
get "$N/Senate_2019/Senate%20Consensus%20Nonpartisan%20Map%20v3_Shapefile.zip" s2019.zip
get "$N/Senate_2022/SL%202022-2%20Senate%20-%20Shapefile.zip" s2022.zip
get "$N/Senate_2023/SL%202023-146%20Senate%20-%20Shapefile.zip" s2023.zip
ls -la out >> out/log.txt
