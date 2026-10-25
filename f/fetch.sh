set -x
O=f/out1; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get(){ curl -sSL --compressed -m 60 -A "$UA" -o "$O/$1" -w "$1 %{http_code} %{size_download} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
get oh_results.html https://www.ohiosos.gov/elections/election-results-and-data/
get oh_2024.html https://www.ohiosos.gov/elections/election-results-and-data/2024-official-elections-results/
get oh_2022.html https://www.ohiosos.gov/elections/election-results-and-data/2022-official-elections-results/
get oh_live.html https://liveresults.ohiosos.gov/
get oh_live2.html https://liveresults.ohiosos.gov/Api/v1/
get oh_hist.html https://www.ohiosos.gov/elections/election-results-and-data/historical-election-comparisons/
get tx_elchist.html "https://elections.sos.state.tx.us/index.htm"
get tx_elchist2.html "https://elections.sos.state.tx.us/elchist.exe"
get tx_tlc.html "https://data.capitol.texas.gov/organization/tlc"
get tx_tlc2.html "https://data.capitol.texas.gov/dataset?q=general+election+returns"
get tx_hist.html "https://www.sos.state.tx.us/elections/historical/elections.shtml"
