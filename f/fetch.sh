#!/bin/bash
# round 8: Internet Archive copies of the Crane A1 page and files
O=f/out8; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
C="https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,original,statuscode,length&collapse=urlkey&matchType=prefix"
curl -sS -m 180 "$C&url=michigan.gov/micrc/-/media/Project/Websites/MiCRC/405CraneA1/" > cdx_crane.txt 2>>err.txt
curl -sS -m 180 "$C&url=michigan.gov/micrc/mapping-process-2024" > cdx_pages.txt 2>>err.txt
curl -sS -m 180 "$C&url=www.michigan.gov/micrc/-/media/Project/Websites/MiCRC/405" > cdx_405.txt 2>>err.txt
ts=$(grep -i 'final-remedial-state-senate' cdx_pages.txt | awk '$3==200{print $1; exit}')
[ -n "$ts" ] && curl -sSL -m 200 -o sen_page.html "https://web.archive.org/web/${ts}id_/https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan"
for h in $(grep -oiE '/micrc/-/media/[^"]*405CraneA1[^"]*' sen_page.html cdx_crane.txt cdx_405.txt 2>/dev/null | sed 's/^[^:]*://; s/&amp;/\&/g' | grep -iE 'zip|shape|shp' | sort -u | head -5); do
  u="https://www.michigan.gov${h#*michigan.gov}"; case $h in /*) u="https://www.michigan.gov$h";; esac
  curl -sSL -A "$UA" -m 200 -o "crane_$(basename ${h%%\?*})" -w "direct $u %{http_code} %{size_download}\n" "$u" >> log.txt
done
echo done >> log.txt; ls -la > ls.txt
