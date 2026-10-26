O=f/out5; mkdir -p $O
for f in cb_2018_55_sldl_500k cb_2018_55_sldu_500k cb_2022_55_sldl_500k cb_2022_55_sldu_500k cb_2024_55_sldl_500k cb_2024_55_sldu_500k; do y=${f:3:4}; curl -sSL -m 300 -o $O/$f.zip -w "$f %{http_code} %{size_download}\n" https://www2.census.gov/geo/tiger/GENZ$y/shp/$f.zip >> $O/log.txt; done
