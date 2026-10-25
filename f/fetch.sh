O=f/out6; mkdir -p $O
for y in 2016 2018 2020 2022 2024; do
  curl -s -m 120 "https://web.archive.org/cdx/search/cdx?url=ohiosos.gov/globalassets/elections/$y/gen/*&output=txt&fl=original,statuscode,mimetype,timestamp&collapse=urlkey&limit=400" > $O/cdx_$y.txt
  curl -s -m 120 "https://web.archive.org/cdx/search/cdx?url=www.sos.state.oh.us/globalassets/elections/$y/gen/*&output=txt&fl=original,statuscode,mimetype,timestamp&collapse=urlkey&limit=400" >> $O/cdx_$y.txt
done
curl -s -m 120 "https://web.archive.org/cdx/search/cdx?url=ohiosos.gov/elections/election-results-and-data/20*&output=txt&fl=original,statuscode,timestamp&collapse=urlkey&limit=200" > $O/cdx_pages.txt
wc -l $O/* > $O/log.txt
