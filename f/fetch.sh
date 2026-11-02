#!/bin/bash
# round 3: election-night files (2026 general, Aug 2026 primary for rehearsal)
O=f/out3; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -D "$1.hdr" -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
B=https://flelectionfiles.floridados.gov/enightfilespublic
for f in 20261103_ElecResultsFL.txt 20261103_ElecResultsFL_PipeDlm_Info.txt 20261103_ElecResultsFL_PipeDlm_Votes.txt ResultsFileLayoutPipeDelimited.pdf 20260818_ElecResultsFL.txt 20260818_ElecResultsFL_PipeDlm_Info.txt 20260818_ElecResultsFL_PipeDlm_Votes.txt 20241105_ElecResultsFL.txt; do get $f $B/$f; done
ls -la > ls.txt
