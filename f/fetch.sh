O=f/out7; mkdir -p $O
for pre in elections.wi.gov/sites/default/files/documents/ elections.wi.gov/sites/default/files/; do
  curl -s -m 300 "https://web.archive.org/cdx/search/cdx?url=${pre}*&output=txt&fl=original,statuscode,timestamp&collapse=urlkey&filter=statuscode:200&from=2026&limit=20000" >> $O/cdx2026.txt
done
wc -l $O/cdx2026.txt > $O/log.txt
grep -iE "candidate|tracking|ballot|partisan|primary|november" $O/cdx2026.txt | head -80 >> $O/log.txt
