#!/bin/bash
# round 2: Internet Archive index of Michigan results files; MICRC remedial plan pages
O=f/out2; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 120 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
C="https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode,length&collapse=urlkey"
get cdx_mie.txt "$C&url=mielections.us/election/results/*"
get cdx_mie_data.txt "$C&url=mielections.us/election/results/DATA/*"
get cdx_boe.txt "$C&url=miboecfr.nictusa.com/election/*"
get cdx_boe2.txt "$C&url=miboecfr.nictusa.com/cgi-bin/cfr/*"
get micrc_sen.html https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan
get micrc_house.html https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-house-plan
get micrc_2024.html https://www.michigan.gov/micrc/mapping-process-2024
ls -la > ls.txt
