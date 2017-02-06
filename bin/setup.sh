#!/usr/bin/env bash

# todo: detect OS and install system packages accordingly
sudo apt install git pyth on python-pip virtualenv  # deb

virtualenv venv
source venv/bin/activate
pip install --upgrade colorama termcolor requests python-dateutil python-slugify google-api-python-client