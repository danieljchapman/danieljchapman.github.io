O=f/out5; mkdir -p $O
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1
sudo apt-get install -y -qq xvfb >/dev/null 2>&1
xvfb-run -a python3 f/p5.py $O > $O/run.txt 2>&1
ls -la $O >> $O/run.txt
