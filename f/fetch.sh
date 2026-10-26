O=f/out1; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
for u in https://elections.wi.gov/ https://elections.wi.gov/elections/election-results; do curl -sSL -m 60 -A "$UA" -o /dev/null -w "$u %{http_code} %{size_download}\n" "$u" >> $O/log.txt 2>&1; done
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 && python3 f/p1.py $O >> $O/log.txt 2>&1
