import json,subprocess,urllib.parse,re,time,os,io,html
from PIL import Image
UA='TXElectionDashboard/1.0 (https://danieljchapman.github.io; election results site)'
CM='https://commons.wikimedia.org/w/api.php'
def api(**p):
    p.update(format='json',formatversion='2'); url=CM+'?'+urllib.parse.urlencode(p)
    for i in range(25):
        r=subprocess.run(['curl','-s','-m','40','-A',UA,'-w','\n%{http_code}',url],capture_output=True)
        body,_,code=r.stdout.rpartition(b'\n')
        if code==b'200':
            try: return json.loads(body)
            except Exception: pass
        time.sleep(min(180,5*2**i))
    raise RuntimeError('commons unavailable')
def text(h): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',h or ''))).strip()
found=json.load(open('found.json'))
want={v['image']:n for n,v in found.items() if v['image']}
info={}
names=list(want)
for i in range(0,len(names),40):
    d=api(action='query',titles='|'.join('File:'+f for f in names[i:i+40]),prop='imageinfo',iiprop='url|extmetadata',iiurlwidth='400')
    norm={x['to']:x['from'] for x in d.get('query',{}).get('normalized',[])}
    for p in d.get('query',{}).get('pages',[]):
        t=norm.get(p['title'],p['title'])[5:]
        if p.get('missing') or not p.get('imageinfo'): info[t]={'ok':False,'why':'not on Commons (non-free or local file)'}; continue
        ii=p['imageinfo'][0]; m=ii.get('extmetadata',{})
        g=lambda k:(m.get(k) or {}).get('value','')
        lic=text(g('LicenseShortName'))
        ok=bool(re.match(r'(public domain|pd\b|pd-|cc0|cc[ -]by(-sa)?( \d\.\d)?( [a-z]+)?$)',lic.lower())) and not re.search(r'\bnc\b|\bnd\b',lic.lower())
        info[t]={'ok':ok,'why':'' if ok else 'license: '+lic,'license':lic,'license_url':g('LicenseUrl'),'artist':text(g('Artist'))[:120],'credit':text(g('Credit'))[:160],
                 'page':ii.get('descriptionurl'),'thumb':ii.get('thumburl'),'w':ii.get('thumbwidth'),'h':ii.get('thumbheight'),'restrictions':g('Restrictions')}
    time.sleep(3)
os.makedirs('img',exist_ok=True)
res={}
for f,n in want.items():
    inf=info.get(f) or {'ok':False,'why':'no info'}
    if inf['ok']:
        slug=re.sub(r'[^a-z0-9]+','-',n.lower()).strip('-')
        path=f'img/{slug}.jpg'
        if not os.path.exists(path):
            for k in range(12):
                r=subprocess.run(['curl','-s','-m','60','-A',UA,'-w','\n%{http_code}',inf['thumb']],capture_output=True)
                body,_,code=r.stdout.rpartition(b'\n')
                if code==b'200': break
                time.sleep(min(120,5*2**k))
            r=type('R',(),{'stdout':body})
            try:
                im=Image.open(io.BytesIO(r.stdout)).convert('RGB'); w,h=im.size; ar=168/206
                if w/h>ar: cw=int(h*ar); box=((w-cw)//2,0,(w-cw)//2+cw,h)
                else: ch=int(w/ar); y0=int((h-ch)*0.15); box=(0,y0,w,y0+ch)
                im.crop(box).resize((168,206),Image.LANCZOS).save(path,'JPEG',quality=80,optimize=True,progressive=True)
            except Exception as e: inf={'ok':False,'why':'download failed: '+str(e)[:60]}
            time.sleep(2)
        if inf['ok']: inf['file']=path
    res[n]={**inf,'image':f,'title':found[n]['title'],'cand':found[n]['cand']}
json.dump(res,open('photos.json','w'),indent=1)
ok=[n for n,v in res.items() if v['ok']]
print('images',len(want),'usable',len(ok))
import collections; print(collections.Counter(v['why'] for v in res.values() if not v['ok']).most_common(8))
print(collections.Counter(v['license'] for v in res.values() if v['ok']).most_common(10))
