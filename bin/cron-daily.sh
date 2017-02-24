#!/usr/bin/env bash

# Back up the captions, commit them to git and push to github.
# Don't run this if you don't know what you are doing.
# Look at backup.sh or youtube.py instead.

# A script to run as a scheduled CRON task, every day at 23:50
# 50 23 * * * web bin/cron-daily.sh > /dev/null 2> /dev/null

today="$(date +'%A %d %B %Y')"
title="JLM Captions Backup"
email="antoine.goutenoir@gmail.com"


source venv/bin/activate

# Don't do a pull, it might require human interaction
# git pull origin master
# Instead, fetch and reset
# git fetch origin master
# git reset --hard FETCH_HEAD
# git clean -df
# Actually, do neither, as too many people have write access to the repo.

python bin/youtube.py --action download &> download.log

if [ $? -ne 0 ] ; then
  cat download.log | mail -s "${title} Download Failure" ${email}
  exit 1
fi

git add subtitles

git commit -m "Sauvegarde du ${today}."

git push origin master &> git-push.log

if [ $? -ne 0 ] ; then
  cat git-push.log | mail -s "${title} Push Failure" ${email}
  exit 1
fi