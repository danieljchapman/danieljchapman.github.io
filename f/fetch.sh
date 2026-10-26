O=f/out3; mkdir -p $O
for pre in elections.wi.gov/sites/default/files/ elections.wi.gov/sites/elections.wi.gov/files/ elections.wi.gov/sites/electionsuat.wi.gov/files/ ; do
  for i in 1 2 3; do
    curl -s -m 300 "https://web.archive.org/cdx/search/cdx?url=${pre}*&output=txt&fl=original,statuscode,mimetype,timestamp&collapse=urlkey&filter=statuscode:200&limit=60000" > $O/cdx_tmp.txt
    if head -c 20 $O/cdx_tmp.txt | grep -q "^http"; then break; fi; sleep 20
  done
  grep -iE "\.xlsx?($|\?| )" $O/cdx_tmp.txt >> $O/cdx_xlsx.txt
  wc -l $O/cdx_tmp.txt >> $O/log.txt
done
rm -f $O/cdx_tmp.txt
grep -ciE "ward" $O/cdx_xlsx.txt >> $O/log.txt
