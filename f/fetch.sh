#!/bin/bash
# round 3: latest archived copy of each certified county results file
O=f/out3; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
for y in 2016 2018 2020 2022 2024; do
  for f in ${y}GEN_MI_CENR_BY_COUNTY.xls ${y}GEN_MI_CENR_BY_COUNTY.txt ${y}GEN_MI_CENR_BY_COUNTY.csv; do
    u=mielections.us/election/results/DATA/$f
    curl -sS -m 120 "https://web.archive.org/cdx/search/cdx?url=$u&output=txt&fl=timestamp,statuscode,length,digest" > cdx_$f.txt 2>>err.txt
    ts=$(awk '$2==200{t=$1} END{print t}' cdx_$f.txt)
    [ -n "$ts" ] && curl -sSL -A "$UA" -m 300 -o $f -w "$f $ts %{http_code} %{size_download}\n" "https://web.archive.org/web/${ts}id_/https://$u" >> log.txt 2>>err.txt
  done
done
echo done >> log.txt
ls -la > ls.txt
