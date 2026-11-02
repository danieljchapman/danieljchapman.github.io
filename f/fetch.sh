#!/bin/bash
# round 4: candidate list forms (to find unopposed winners)
O=f/out4; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
get dl_form.html https://dos.elections.myflorida.com/candidates/downloadcanlist.asp
get canlist.html https://dos.elections.myflorida.com/candidates/canlist.asp
get cand_home.html https://dos.elections.myflorida.com/candidates/
ls -la > ls.txt
