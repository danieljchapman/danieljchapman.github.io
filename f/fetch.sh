O=f/out6; mkdir -p $O
u=$(grep -i "Recount%2011-30-20%20final" f/out3/cdx_xlsx.txt | sort -k4 | tail -1)
set -- $u
curl -sSL -m 300 -o "$O/2020_recount_final.xlsx" -w "%{http_code} %{size_download}\n" "https://web.archive.org/web/${4}id_/$1" > $O/log.txt
