O=f/out8; mkdir -p $O
curl -sSL -m 600 -o $O/tl_2020_39_tabblock20.zip https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_39_tabblock20.zip -w "%{http_code} %{size_download}\n" > $O/log.txt
pip install -q geopandas pyogrio openpyxl >> $O/log.txt 2>&1
python3 f/dissolve.py $O >> $O/log.txt 2>&1
rm -f $O/tl_2020_39_tabblock20.zip
ls -la $O >> $O/log.txt
