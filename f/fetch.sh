#!/bin/bash
# round 2: the Secretary of State's official general-election results files, 2016-2024
O=f/out2; mkdir -p $O
python3 f/dl.py $O > $O/log.txt 2> $O/err.txt
