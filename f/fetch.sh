O=f/out8; mkdir -p $O
grep -E "August%202026%20Partisan%20Primary_Summary|D\.%20Ballot%20Access%20Report|Ballot%20Access%20Report" f/out7/cdx2026.txt | sort -u | while read u s t; do
  n=$(basename "$u" | sed 's/%20/_/g'); curl -sSL -m 300 -o "$O/$n" -w "$n %{http_code} %{size_download}\n" "https://web.archive.org/web/${t}id_/$u" >> $O/log.txt; sleep 3; done
grep -i "ballot\|candidate" f/out7/cdx2026.txt | sed 's#.*/files/##' | sort -u > $O/related.txt
