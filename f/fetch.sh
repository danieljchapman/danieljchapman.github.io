#!/bin/bash
# round 1: Census shapes, MEDSL file lists, Iowa SOS results pages
O=f/out1; mkdir -p $O
G=https://www2.census.gov/geo/tiger/GENZ
dl() { curl -sSL -m 300 -A 'Mozilla/5.0' -o "$O/$2" "$1" -w "%{http_code} %{size_download} $2\n" >> $O/log.txt 2>>$O/err.txt; }
dl ${G}2020/shp/cb_2020_us_county_500k.zip cb_2020_us_county_500k.zip
dl ${G}2018/shp/cb_2018_us_cd116_500k.zip cb_2018_us_cd116_500k.zip
dl ${G}2022/shp/cb_2022_us_cd118_500k.zip cb_2022_us_cd118_500k.zip
for y in 2018 2022 2024; do dl ${G}$y/shp/cb_${y}_19_sldl_500k.zip cb_${y}_sldl.zip; dl ${G}$y/shp/cb_${y}_19_sldu_500k.zip cb_${y}_sldu.zip; done
for r in 2016-elections-official 2018-elections-official 2020-elections-official 2022-elections-official; do
  for b in main master; do curl -sS -m 60 -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/MEDSL/$r/git/trees/$b?recursive=1" | python3 -c "import json,sys
d=json.load(sys.stdin); print('\n'.join(x['path']+' '+str(x.get('size','')) for x in d.get('tree',[]) if 'ia' in x['path'].lower().split('/')[-1][:12]))" > $O/medsl_${r}_$b.txt 2>>$O/err.txt; done
done
for u in https://sos.iowa.gov/elections/results/index.html https://sos.iowa.gov/elections/electionresults/index.html https://sos.iowa.gov/elections/results/ https://electionresults.iowa.gov/ https://sos.iowa.gov/; do
  n=$(echo $u | tr -c 'a-z0-9' '_'); curl -sSL -m 60 -A 'Mozilla/5.0' -o $O/$n.html -w "%{http_code} %{url_effective} $n\n" "$u" >> $O/log.txt 2>>$O/err.txt
done
ls -la $O > $O/ls.txt
