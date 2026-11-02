#!/bin/bash
# round 5: candidate lists (all statuses) for federal, governor & cabinet, legislature
O=f/out5; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
get(){ curl -sSL -A "$UA" -m 300 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt || echo "$1 FAIL $2" >> log.txt; }
for e in 20161108-GEN 20181106-GEN 20201103-GEN 20221108-GEN 20241105-GEN 20261103-GEN 20261103-S01; do
  for o in FED CAB LEG; do
    get can_${e}_$o.txt -X POST -e https://dos.elections.myflorida.com/candidates/downloadcanlist.asp -d "elecID=$e&office=$o&status=All&cantype=STA&FormSubmit=Download+Candidate+List" https://dos.elections.myflorida.com/candidates/extractCanList.asp
  done
done
ls -la > ls.txt
