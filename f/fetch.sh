#!/bin/bash
# round 3: archived Iowa SOS results files (Internet Archive raw copies) and Clarity (electionresults.iowa.gov) 2024/2026 files
O=f/out3; mkdir -p $O/wb
python3 f/pw3.py $O > $O/pw_log.txt 2>&1
while read t u; do
  n=$(echo "$u" | sed -E 's#^https?://sos.iowa.gov/elections/##; s#%20#_#g; s#/#__#g')
  for a in 1 2 3; do
    code=$(curl -sSL -m 120 -o "$O/wb/$n" -w '%{http_code}' "https://web.archive.org/web/${t}id_/$u" 2>>$O/err.txt)
    [ "$code" = 200 ] && break; sleep $((a * 10))
  done
  echo "$code $n" >> $O/log.txt
done < f/wb_list.txt
ls -la $O $O/wb > $O/ls.txt
