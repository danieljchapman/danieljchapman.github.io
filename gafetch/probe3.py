import gzip, json, os, subprocess
OUT = 'gafetch/out3'; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'a')
def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.write(s + '\n'); LOG.flush()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
SLUGS = ['2016NovGen', '2016MayGenPri', '2018NovGen', '2018DecGenRun', '2018GenPri', '2020NovGen', '2020NovGenRec', '2020DecStateRun', '2020AugPPP', '2021JanFedRun',
         '2022NovGen', '2022DecGenRun', '2022MayGenPri', '2024NovGen', '2024MayGenPri', 'MunicipalGeneralSpecialElectionPSC11042025', 'December2nd2025Runoffs',
         'GeneralPrimary51926', '11032026GeneralAndSpecialElection']
def get(url):
    p = subprocess.run(['curl', '-s', '-L', '--compressed', '-m', '600', '-A', UA, '-w', '\n%{http_code}', url], capture_output=True)
    body, _, code = p.stdout.rpartition(b'\n')
    return code.decode(), body
for slug in SLUGS:
    code, body = get(f'https://results.sos.ga.gov/results/public/api/elections/Georgia/{slug}/data')
    if code != '200': log(slug, 'data', code); continue
    d = json.loads(body)
    open(os.path.join(OUT, f'data_{slug}.json.gz'), 'wb').write(gzip.compress(body))
    path = d['jurisdiction'].get('mediaExportPath')
    log(slug, 'data ok', len(body), 'export', path)
    if not path: continue
    for base in ['https://results.sos.ga.gov/cdn/results/', 'https://results.sos.ga.gov/results/public/cdn/', 'https://results.sos.ga.gov/']:
        code, body = get(base + path)
        log('  try', base + path, code, len(body), body[:60] if code != '200' else '')
        if code == '200' and body[:1] in (b'{', b'['):
            gz = gzip.compress(body)
            log('  saved', len(body), 'gz', len(gz))
            if len(gz) < 90_000_000:
                open(os.path.join(OUT, f'export_{slug}.json.gz'), 'wb').write(gz)
            break
