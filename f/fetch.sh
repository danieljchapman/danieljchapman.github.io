O=f/out9; mkdir -p $O
curl -s -m 120 "https://web.archive.org/cdx/search/cdx?url=sos.state.oh.us/globalassets/elections/2014/gen/*&output=txt&fl=original,statuscode,timestamp&collapse=urlkey&limit=200" > $O/cdx_2014a.txt
curl -s -m 120 "https://web.archive.org/cdx/search/cdx?url=ohiosos.gov/globalassets/elections/2014/gen/*&output=txt&fl=original,statuscode,timestamp&collapse=urlkey&limit=200" > $O/cdx_2014b.txt
cat $O/cdx_2014*.txt | grep -i xls | grep -iE "county|statewide" | grep -v -i precinct | while read u s t; do n=$(basename $u); curl -sSL -m 300 -o "$O/2014_$n" "https://web.archive.org/web/${t}id_/$u" -w "$n %{http_code} %{size_download}\n" >> $O/log.txt; sleep 3; done
