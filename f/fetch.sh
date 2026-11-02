#!/bin/bash
# round 4: MICRC remedial Senate plan (Crane A1) shapefile; 2024 archived results variants
O=f/out4; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 200 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
get sen.html https://michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan
get house.html https://michigan.gov/micrc/mapping-process-2024/final-remedial-state-house-plan
for p in sen house; do
  for h in $(grep -oiE 'href="[^"]*\.zip[^"]*"' $p.html | sed 's/href="//; s/"$//; s/&amp;/\&/g' | sort -u); do
    case $h in http*) u=$h;; *) u=https://michigan.gov$h;; esac
    n=$(basename "${h%%\?*}"); get "${p}_$n" "$u"
  done
done
curl -sS -m 120 "https://web.archive.org/cdx/search/cdx?url=mielections.us/election/results/DATA/2024*&matchType=prefix&output=txt&fl=timestamp,original,statuscode,length" > cdx_2024.txt
ls -la > ls.txt
