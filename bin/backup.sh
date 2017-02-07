#!/usr/bin/env bash

# virtualenv = suit up !
source venv/bin/activate

# go fishing
python bin/youtube.py --action download $@
