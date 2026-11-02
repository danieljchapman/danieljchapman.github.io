#!/bin/bash
# round 9: archived Crane A1 page (retries), then its shapefile link
O=f/out9; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
for i in 1 2 3 4 5 6; do
  curl -sSL -m 200 -o sen_page.html "https://web.archive.org/web/20240709005747id_/https://www.michigan.gov/micrc/mapping-process-2024/final-remedial-state-senate-plan"
  grep -q '405' sen_page.html && break; sleep 30
done
grep -oiE 'href="[^"]*"' sen_page.html | sed 's/href="//; s/"$//; s/&amp;/\&/g' | grep -i media > links.txt
for h in $(grep -iE 'shape|zip|shp' links.txt | head -5); do
  case $h in http*) u=$h;; *) u="https://www.michigan.gov$h";; esac
  for t in 1 2 3; do curl -sSL -A "$UA" -m 200 -o "crane_shp.zip" -w "direct $u %{http_code} %{size_download}\n" "$u" >> log.txt && file crane_shp.zip | grep -qi zip && break; sleep 10; done
  file crane_shp.zip | grep -qi zip || curl -sSL -m 300 -o crane_shp.zip -w "archive %{http_code} %{size_download}\n" "https://web.archive.org/web/2024id_/$u" >> log.txt
done
echo done >> log.txt; ls -la > ls.txt
