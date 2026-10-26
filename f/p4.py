import sys, re, subprocess, urllib.parse, os, time, json
O=sys.argv[1]; os.makedirs(O,exist_ok=True)
NAMES=['Statewide Results All Offices (post-Presidential recount).xlsx','County by County Report President of the United States Recount.xlsx',
'County by County Report US Senate.xlsx','Ward by Ward Report-Assembly.xlsx','Ward by Ward Report-Assembly_0.xlsx','Ward by Ward Report-State Senate.xlsx',
'Ward by Ward Report - State Senator.xlsx','Ward by Ward Report - State Senate.xlsx','Ward by Ward Report -US Senator.xlsx',
'County by County Report-2018 Gen Election-State Constitutional Offices.xlsx','County by County Report-Gen Elections-US Senate.xlsx',
'County by County Report-Gen Election-Assembly.xlsx','County by County Report-Gen Election-State Senator.xlsx','Summary Results-2018 Gen Election.xlsx',
'County by County Report all offices.xlsx','County by County Report-President.xlsx','County by County Report_President.xlsx','County by County Report.xlsx',
'Ward by Ward Report-State Senate (SD32 under recount).xlsx','Ward by Ward Report.xlsx','Ward by Ward Report_0.xlsx','Ward by Ward Report_1.xlsx',
'County by County Report_Attorney General_0.xlsx','County by County Report_Governor_1.xlsx','County by County Report_Representative to the Assembly_0.xlsx',
'County by County Report_Secretarry of State_0.xlsx','County by County Report_State Senator_0.xlsx','County by County Report_State Treasurer_0.xlsx',
'County by County Report_US Senate_0.xlsx','County by County Report_US Senate.xlsx','Statewide Summary Results_0.xlsx','County by County Report-Congress.xlsx']
best={}
for l in open(sys.argv[2]):
    p=l.split()
    if len(p)<4: continue
    u,t=p[0],p[3]; n=urllib.parse.unquote(u.split('/files/')[-1]).split('/')[-1]
    if n in NAMES:
        k=(n,u.split('/files/')[-1].startswith('documents/'))
        if k not in best or t>best[k][1]: best[k]=(u,t)
import openpyxl
summary={}
for (n,doc),(u,t) in sorted(best.items()):
    fn=('D_' if doc else '')+re.sub(r'[^A-Za-z0-9._-]+','_',n)
    for i in range(3):
        r=subprocess.run(['curl','-sSL','-m','300','-o',f'{O}/{fn}','-w','%{http_code}',f'https://web.archive.org/web/{t}id_/{u}'],capture_output=True,text=True)
        if r.stdout=='200' and open(f'{O}/{fn}','rb').read(2)==b'PK': break
        time.sleep(10)
    info={'url':u,'ts':t,'http':r.stdout,'size':os.path.getsize(f'{O}/{fn}') if os.path.exists(f'{O}/{fn}') else 0,'sheets':{}}
    try:
        wb=openpyxl.load_workbook(f'{O}/{fn}',read_only=True)
        for ws in wb.worksheets[:6]:
            info['sheets'][ws.title]=[[str(c)[:60] if c is not None else '' for c in row[:8]] for row in ws.iter_rows(max_row=12,values_only=True)]
    except Exception as e: info['err']=str(e)[:200]
    summary[fn]=info; print(fn,info['http'],info['size'])
    time.sleep(3)
json.dump(summary,open(O+'/summary.json','w'),indent=1)
