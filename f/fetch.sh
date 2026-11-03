#!/bin/bash
# round 3: run the Kansas election-night importer from main on a GitHub runner (no publishing)
O=f/out3; mkdir -p $O
git fetch -q --depth 1 origin main && git checkout FETCH_HEAD -- ks tools
start=$(date +%s)
python3 ks/tools/ks_live.py --out $O > $O/log.txt 2> $O/err.txt; echo "exit $? in $(( $(date +%s) - start ))s" >> $O/log.txt
wc -l $O/live_2026.csv >> $O/log.txt
git reset -q ks tools; rm -rf ks tools
