#!/usr/bin/env bash

export PYTHONIOENCODING="utf8"

source venv/bin/activate

if [ $? -ne 0 ] ; then
  echo -e "Set up a virtualenv first. See 'setup.sh'."
  exit 1
fi

python bin/youtube.py --action download $@
