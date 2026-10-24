#!/usr/bin/env bash
# run 4: election-night importer against the live state site
mkdir -p gafetch/out4
python3 ga/tools/ga_live.py --out gafetch/out4 > gafetch/out4/log.txt 2>&1; echo "exit $?" >> gafetch/out4/log.txt
