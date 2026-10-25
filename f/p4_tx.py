# Texas SOS official county results for President (2000-2016) + TLC 2024 president by county
import re, subprocess, sys, os, csv, io, zipfile, collections
O=sys.argv[1]; UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
def get(u, binary=False):
    p=subprocess.run(['curl','-sSL','--compressed','-m','300','-A',UA,u],capture_output=True)
    return p.stdout if binary else p.stdout.decode('latin-1')
B='https://elections.sos.state.tx.us/'
for eid in [82,114,141,164,319]:
    t=get(f'{B}elchist{eid}_raceselect.htm'); open(f'{O}/tx_{eid}_raceselect.htm','w').write(t)
    opts=re.findall(r'<OPTION[^>]*value="([^"]+)"[^>]*>([^<]*)', t, re.I)
    pres=[v for v,n in opts if 'president' in n.lower()]
    print(eid, len(opts), pres[:3], [n.strip() for v,n in opts[:5]])
    # also save the JS to understand the URL pattern
    for v in pres[:1]:
        for pat in [f'elchist{eid}_race{v}.htm', f'elchist{eid}_{v}.htm', v]:
            u=B+pat if not pat.startswith('http') else pat
            r=get(u); 
            if len(r)>2000 and 'ANDERSON' in r.upper():
                open(f'{O}/tx_{eid}_pres.htm','w').write(r); print(' got',u); break
            else: print(' miss',u,len(r))
z=zipfile.ZipFile(io.BytesIO(get('https://data.capitol.texas.gov/dataset/35b16aee-0bb0-4866-b1ec-859f1f044241/resource/e1cd6332-6a7a-4c78-ad2a-852268f6c7a2/download/2024-general-vtds-election-data.zip',True)))
for n in z.namelist():
    if re.search(r'20(12|16|20|24)_General_Election_Returns', n):
        agg=collections.Counter()
        for r in csv.DictReader(io.TextIOWrapper(z.open(n),'utf-8',errors='replace')):
            if r['Office']=='President': agg[(r['County'],r['FIPS'],r['Name'],r['Party'])]+=int(r['Votes'] or 0)
        w=csv.writer(open(f'{O}/tlc_pres_{n[:4]}.csv','w')); w.writerow(['county','fips','name','party','votes'])
        for k,v in sorted(agg.items()): w.writerow(list(k)+[v])
        print(n, sum(agg.values()))
