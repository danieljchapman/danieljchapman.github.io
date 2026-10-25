O=f/out3; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get(){ curl -sSL --compressed -m 300 -A "$UA" -o "$O/$1" -w "$1 %{http_code} %{size_download} %{url_effective}\n" "$2" >> $O/log.txt 2>>$O/err.txt; }
get countypres.tab "https://dataverse.harvard.edu/api/access/datafile/13573089"
gzip -9 $O/countypres.tab
get tlc2020.zip "https://data.capitol.texas.gov/dataset/35b16aee-0bb0-4866-b1ec-859f1f044241/resource/5af9f5e2-ca14-4e5d-880e-3c3cd891d3ed/download/2020-general-vtd-election-data-2020.zip"
get tlc2024.zip "https://data.capitol.texas.gov/dataset/35b16aee-0bb0-4866-b1ec-859f1f044241/resource/e1cd6332-6a7a-4c78-ad2a-852268f6c7a2/download/2024-general-vtds-election-data.zip"
for z in tlc2020 tlc2024; do mkdir -p $O/$z; unzip -l $O/$z.zip > $O/$z.list; unzip -o -q $O/$z.zip -d $O/$z '*eneral*' 2>/dev/null; unzip -o -q $O/$z.zip -d $O/$z '*President*' '*ounty*' 2>/dev/null; rm $O/$z.zip; done
du -sh $O/*
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 && python3 f/probe3.py $O > $O/pw.txt 2>&1
ls -la $O >> $O/log.txt
