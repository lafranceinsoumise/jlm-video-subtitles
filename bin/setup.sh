#!/usr/bin/env bash

if cat /etc/*release | grep ^NAME | grep Ubuntu ; then
    sudo apt install git python python-pip virtualenv
elif cat /etc/*release | grep ^NAME | grep Debian ; then
    sudo aptitude install git python python-pip virtualenv
fi  # ... add your OS here

virtualenv venv
source venv/bin/activate
pip install --upgrade colorama termcolor requests \
                      python-dateutil isodate strict-rfc3339 \
                      python-slugify google-api-python-client PyGithub

# If "InsecurePlatformWarning: A true SSLContext object is not available."
# pip install requests[security]

echo -e "Done."