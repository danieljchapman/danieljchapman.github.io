O=f/out4; mkdir -p $O
pip install -q openpyxl >/dev/null 2>&1
python3 f/p4.py $O f/out3/cdx_xlsx.txt > $O/log.txt 2>&1
