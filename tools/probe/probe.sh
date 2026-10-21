#!/usr/bin/env bash
# Fetch El Paso and Dallas early-vote summary reports and save them as text for review (summary reports only).
set -u
cd "$(dirname "$0")"
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
mkdir -p out
curl -s -L -m 60 -A "$UA" https://epcountyvotestx.gov/voter-information/current-election -o out/ep_page.html
grep -o 'https://ep-county-elections-production[^"]*Statistics[^"]*' out/ep_page.html | sed 's/&amp;/\&/g' | sort -u > out/ep_links.txt
i=0; while read -r u; do i=$((i+1)); curl -s -L -m 60 -A "$UA" "$u" -o out/ep_$i.pdf; echo "$u" > out/ep_$i.url; pdftotext -layout out/ep_$i.pdf out/ep_$i.txt; rm -f out/ep_$i.pdf; done < out/ep_links.txt
curl -s -L -m 60 -A "$UA" https://www.dallascountyvotes.org/election-results/historical/november-3-2026-general-and-joint-election/ -o out/dal_page.html
grep -o 'https://www.dallascountyvotes.org/wp-content/uploads/[^"]*Turnout-By-Date-and-Location[^"]*\.xlsx' out/dal_page.html | sort -u > out/dal_links.txt
i=0; while read -r u; do i=$((i+1)); curl -s -L -m 60 -A "$UA" "$u" -o out/dal_$i.xlsx; echo "$u" > out/dal_$i.url
  python3 -c "
import openpyxl,sys,csv
wb=openpyxl.load_workbook(sys.argv[1],read_only=True,data_only=True)
w=csv.writer(open(sys.argv[2],'w'))
for ws in wb.worksheets:
    w.writerow(['## sheet',ws.title])
    for r in ws.iter_rows(values_only=True): w.writerow(r)
" out/dal_$i.xlsx out/dal_$i.csv; rm -f out/dal_$i.xlsx; done < out/dal_links.txt
ls -la out
