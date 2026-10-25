O=f/out4; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get(){ curl -sSL --compressed -m 300 -A "$UA" -o "$O/$1" -w "$1 %{http_code} %{size_download} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
get countypres.tab "https://dataverse.harvard.edu/api/access/datafile/13573089?format=original"
get countypres2.tab "https://dataverse.harvard.edu/api/access/datafile/13573089?format=tab"
head -c 300 $O/countypres.tab > $O/countypres_head.txt
gzip -9 -f $O/countypres*.tab
mkdir -p $O/shp
for f in cb_2020_us_county_500k cb_2018_39_sldl_500k cb_2018_39_sldu_500k cb_2022_39_sldl_500k cb_2022_39_sldu_500k cb_2024_39_sldl_500k cb_2024_39_sldu_500k cb_2018_us_cd116_500k cb_2022_us_cd118_500k cb_2024_us_cd119_500k; do
  y=${f:3:4}; get shp/$f.zip "https://www2.census.gov/geo/tiger/GENZ$y/shp/$f.zip"; done
python3 f/p4_tx.py $O > $O/tx.txt 2>&1
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 && python3 f/p4_oh.py $O > $O/oh.txt 2>&1
du -sh $O/* >> $O/log.txt
