#!/bin/bash
# round 4: run the Iowa election-night importer from main on a GitHub runner (no publishing)
O=f/out4; mkdir -p $O
git fetch -q --depth 1 origin main && git checkout FETCH_HEAD -- ia tools
start=$(date +%s)
python3 ia/tools/ia_live.py --out $O > $O/log.txt 2> $O/err.txt; echo "exit $? in $(( $(date +%s) - start ))s" >> $O/log.txt
wc -l $O/live_2026.csv >> $O/log.txt
git reset -q ia tools; git checkout -q -- ia tools 2>/dev/null; rm -rf ia tools
