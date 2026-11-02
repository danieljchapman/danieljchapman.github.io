#!/bin/bash
# round 10: run the live importer on a GitHub runner
O=f/out10; mkdir -p $O
python3 f/t/mi_live.py --out $O > $O/log.txt 2> $O/err.txt; echo "exit $?" >> $O/log.txt; wc -l $O/live_2026.csv >> $O/log.txt
