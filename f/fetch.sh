O=f/out9; mkdir -p $O
curl -sSL -m 300 -o "$O/2014_results.xlsx" "https://web.archive.org/web/20200612164020id_/https://www.ohiosos.gov/globalassets/elections/2014/general/results.xlsx" -w "%{http_code} %{size_download}\n" >> $O/log.txt
