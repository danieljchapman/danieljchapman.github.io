O=f/out2; mkdir -p $O
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 && python3 f/p2.py $O > $O/log.txt 2>&1
du -sh $O/* >> $O/log.txt
