#!/bin/bash
# round 6: run the live importer on a GitHub runner against the real 2026 file
O=f/out6; mkdir -p $O
python3 f/t/fl_live.py --out $O > $O/log.txt 2> $O/err.txt; echo "exit $?" >> $O/log.txt
wc -l $O/live_2026.csv >> $O/log.txt
