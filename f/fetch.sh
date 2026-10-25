O=f/out2; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get(){ curl -sSL --compressed -m 120 -A "$UA" -o "$O/$1" -w "$1 %{http_code} %{size_download} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
curl -s https://ifconfig.me > $O/ip.txt
get tlc_comp.html https://data.capitol.texas.gov/dataset/comprehensive-election-datasets-compressed-format
get tlc_api.json "https://data.capitol.texas.gov/api/3/action/package_show?id=comprehensive-election-datasets-compressed-format"
get dv_countypres.json "https://dataverse.harvard.edu/api/datasets/:persistentId?persistentId=doi:10.7910/DVN/VOQCHQ"
get civic_oh.json "https://civicapi.org/api/v2/race/search?country=US&province=OH&startDate=2026-11-03&endDate=2026-11-03&limit=500"
get civic_oh24.json "https://civicapi.org/api/v2/race/search?country=US&province=OH&startDate=2024-11-05&endDate=2024-11-05&limit=500"
get oh_dataohio.html "https://data.ohio.gov/wps/portal/gov/data/search?q=election"
get oh_lsc.html "https://www.legislature.ohio.gov/"
get oh_redistricting.html "https://redistricting.ohio.gov/maps"
get census_sldl.zip "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_39_sldl_500k.zip"
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 && python3 f/probe2.py $O > $O/pw.txt 2>&1
