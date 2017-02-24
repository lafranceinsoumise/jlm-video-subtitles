#!/usr/bin/env bash

# Look up the recently published videos, and create issues in the github repo.

# A script to run as a scheduled CRON task, every hour at the seventh minute
# 07 * * * * web bin/cron-hourly.sh > /dev/null 2> /dev/null

today="$(date +'%A %d %B %Y')"
title="JLM Captions Github Bot"
email="antoine.goutenoir@gmail.com"


source venv/bin/activate

python bin/youtube.py --action github &> github.log

if [ $? -ne 0 ] ; then
  cat github.log | mail -s "${title} Failure" ${email}
  exit 1
fi
