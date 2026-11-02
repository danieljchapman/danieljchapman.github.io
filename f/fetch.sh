#!/bin/bash
# round 1: FL DOS results files, Census shapes, redistricting pages
O=f/out1; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -o "$1" -w "$1 %{http_code} %{size_download}\n" "$2" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
for d in 11/8/2016:20161108 11/6/2018:20181106 11/3/2020:20201103 11/8/2022:20221108 11/5/2024:20241105; do
  md=${d%%:*}; ymd=${d##*:}
  get dl_$ymd.txt "https://results.elections.myflorida.com/downloadresults.asp?ElectionDate=$md&DATAMODE="
  get en_$ymd.txt "https://fldoselectionfiles.elections.myflorida.com/enightfilespublic/${ymd}_ElecResultsFL.txt"
done
get en_20261103.txt "https://fldoselectionfiles.elections.myflorida.com/enightfilespublic/20261103_ElecResultsFL.txt"
get en_20260818.txt "https://fldoselectionfiles.elections.myflorida.com/enightfilespublic/20260818_ElecResultsFL.txt"
get results_home.html "https://results.elections.myflorida.com/"
get archive.html "https://results.elections.myflorida.com/Index.asp?ElectionDate=11/5/2024&DATAMODE="
get dos_archive.html "https://dos.fl.gov/elections/data-statistics/elections-data/election-results-archive/"
get fr_home.html "https://www.floridaredistricting.gov/"
get fr_plans.html "https://www.floridaredistricting.gov/pages/submitted-plans"
get fr_2026.html "https://www.floridaredistricting.gov/pages/2026-congressional-plan"
get flsenate_redis.html "https://www.flsenate.gov/Session/Redistricting"
get flhouse_redis.html "https://www.myfloridahouse.gov/redistricting"
B=https://www2.census.gov/geo/tiger/GENZ
get cb_2020_county.zip ${B}2020/shp/cb_2020_us_county_500k.zip
get cb_2018_cd116.zip ${B}2018/shp/cb_2018_us_cd116_500k.zip
get cb_2022_cd118.zip ${B}2022/shp/cb_2022_us_cd118_500k.zip
for y in 2016 2018 2022 2024; do get cb_${y}_sldu.zip ${B}$y/shp/cb_${y}_12_sldu_500k.zip; get cb_${y}_sldl.zip ${B}$y/shp/cb_${y}_12_sldl_500k.zip; done
get tl_2020_12_tabblock20.zip https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_12_tabblock20.zip
ls -la > ls.txt
