#!/usr/bin/env bash
# Election-night diagnostic: is Florida's results file updating?
mkdir -p f/out; cd f/out; rm -f *
U=https://flelectionfiles.floridados.gov/enightfilespublic
curl -sS -D hdr.txt -o fl.txt "$U/20261103_ElecResultsFL.txt?t=$(date +%s)" ; echo "status: $?" > summary.txt
cat hdr.txt >> summary.txt
python3 - >> summary.txt <<'PY'
import csv
rd=list(csv.DictReader(open('fl.txt',encoding='utf-8',errors='replace'),delimiter='\t',quoting=csv.QUOTE_NONE))
print('rows',len(rd)); print('cols',list(rd[0].keys()) if rd else None)
tot=sum(int(x.get('CanVotes') or 0) for x in rd); print('total votes',tot)
print('dates',{x.get('ElectionDate') for x in rd})
g=[x for x in rd if x.get('RaceCode','').strip()=='GOV']
print('GOV rows',len(g),'votes',sum(int(x['CanVotes'] or 0) for x in g),'prec',sum(int(x['PrecinctsReporting'] or 0) for x in g[::max(1,len({y['CanNameLast'] for y in g}))]))
for x in rd[:3]: print(x)
print('racecodes',sorted({x.get('RaceCode','').strip() for x in rd})[:60])
PY
curl -sS -L "https://floridaelectionwatch.gov/Downloads" -o dl.html; grep -oiE 'href="[^"]+\.(txt|zip|csv|xml|json)[^"]*"' dl.html | sort -u >> summary.txt
curl -sS -L "$U/" -o idx.html; head -c 3000 idx.html >> summary.txt
