#!/bin/bash
# round 2: file lists (MEDSL 2016/2020, OpenElections IA), Wayback index of the SOS results pages, Playwright on the state sites
O=f/out2; mkdir -p $O
for r in MEDSL/2016-elections-official MEDSL/2020-elections-official MEDSL/2016-precinct-returns MEDSL/2020-precincts openelections/openelections-data-ia; do
  n=$(echo $r | tr '/' '_')
  for b in main master; do curl -sS -m 60 -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/$r/git/trees/$b?recursive=1" > $O/tree_${n}_$b.json 2>>$O/err.txt; done
done
curl -sS -m 120 'https://web.archive.org/cdx/search/cdx?url=sos.iowa.gov/elections/results/*&output=json&fl=original,timestamp,statuscode,mimetype&collapse=urlkey&limit=5000' > $O/cdx_results.json 2>>$O/err.txt
curl -sS -m 120 'https://web.archive.org/cdx/search/cdx?url=sos.iowa.gov/elections/pdf/*&output=json&fl=original,timestamp,statuscode,mimetype&collapse=urlkey&limit=10000' > $O/cdx_pdf.json 2>>$O/err.txt
python3 f/pw.py $O > $O/pw_log.txt 2>&1
ls -la $O > $O/ls.txt
