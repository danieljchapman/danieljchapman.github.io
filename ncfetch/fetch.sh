#!/usr/bin/env bash
# Round 4: how the NCSBE election-night site (er.ncsbe.gov) gets its data.
set -u
cd "$(dirname "$0")"
mkdir -p out
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get() { curl -sS -L -g -m 120 -A "$UA" -o "out/$2" -w "$1 %{http_code} %{size_download} %{content_type}\n" "$1" >> out/log.txt 2>&1 || echo "$1 FAILED" >> out/log.txt; }
get "https://er.ncsbe.gov/" er_root.html
get "https://er.ncsbe.gov/?election_dt=03/03/2026&county_id=0&office=FED&contest=0" er_mar.html
for u in $(grep -oE '(src|href)="[^"]+\.(js|json)[^"]*"' out/er_root.html | sed -E 's/^(src|href)="//; s/"$//' | sort -u); do
  case "$u" in http*) full="$u";; /*) full="https://er.ncsbe.gov$u";; *) full="https://er.ncsbe.gov/$u";; esac
  get "$full" "js_$(echo "$u" | tr '/?=&' '____' | tail -c 80)"
done
pip install -q playwright >/dev/null 2>&1 && python -m playwright install --with-deps chromium >/dev/null 2>&1
python - <<'PY' >> out/log.txt 2>&1
from playwright.sync_api import sync_playwright
urls = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.on('request', lambda r: urls.append(r.url))
    pg.goto('https://er.ncsbe.gov/?election_dt=03/03/2026&county_id=0&office=FED&contest=0', timeout=90000)
    pg.wait_for_timeout(12000)
    open('out/er_rendered.txt', 'w').write(pg.inner_text('body')[:20000])
    b.close()
open('out/er_requests.txt', 'w').write('\n'.join(urls))
print('requests', len(urls))
PY
ls -la out >> out/log.txt
