#!/usr/bin/env bash

source venv/bin/activate

if [ $? -ne 0 ] ; then
  echo -e "Set up a virtualenv first. See 'setup.sh'."
  exit 1
fi

python bin/youtube.py --action download $@
