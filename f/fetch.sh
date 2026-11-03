#!/bin/bash
# round 1: Census shapes, file lists, Kansas SOS results pages, Internet Archive index
O=f/out1; mkdir -p $O
G=https://www2.census.gov/geo/tiger/GENZ
dl() { curl -sSL -m 300 -A 'Mozilla/5.0' -o "$O/$2" "$1" -w "%{http_code} %{size_download} $2\n" >> $O/log.txt 2>>$O/err.txt; }
dl ${G}2020/shp/cb_2020_us_county_500k.zip cb_2020_us_county_500k.zip
dl ${G}2018/shp/cb_2018_us_cd116_500k.zip cb_2018_us_cd116_500k.zip
dl ${G}2022/shp/cb_2022_us_cd118_500k.zip cb_2022_us_cd118_500k.zip
for y in 2018 2022 2024; do dl ${G}$y/shp/cb_${y}_20_sldl_500k.zip cb_${y}_sldl.zip; dl ${G}$y/shp/cb_${y}_20_sldu_500k.zip cb_${y}_sldu.zip; done
for r in openelections/openelections-data-ks MEDSL/2018-elections-official MEDSL/2022-elections-official MEDSL/2024-elections-official; do
  n=$(echo $r | tr '/' '_'); for b in main master; do curl -sS -m 60 -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/$r/git/trees/$b?recursive=1" | python3 -c "import json,sys
d=json.load(sys.stdin); print('\n'.join(x['path']+' '+str(x.get('size','')) for x in d.get('tree',[]) if 'ks' in x['path'].lower() or 'kansas' in x['path'].lower() or 'general' in x['path']))" > $O/tree_${n}_$b.txt 2>>$O/err.txt; done
done
for u in 'sos.ks.gov/elections/*' 'www.sos.ks.gov/elections/*' 'kssos.org/elections/*' 'www.kssos.org/elections/*'; do
  n=$(echo "$u" | tr -c 'a-z0-9' '_'); curl -sS -m 180 "https://web.archive.org/cdx/search/cdx?url=$u&output=json&fl=original,timestamp,statuscode,mimetype&collapse=urlkey&limit=20000" > $O/cdx_$n.json 2>>$O/err.txt
done
python3 f/pw.py $O https://sos.ks.gov/elections/elections-results.html https://sos.ks.gov/elections/election-results.html https://www.sos.ks.gov/elections/ > $O/pw_log.txt 2>&1
ls -la $O > $O/ls.txt
