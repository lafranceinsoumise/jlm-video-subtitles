#!/usr/bin/python
# coding=utf-8

# The purpose of the script is to download all the subtitles files from Youtube
# Tested with python 2.7 only.

# Install
# pip install --upgrade colorama termcolor requests
# pip install --upgrade python-dateutil python-slugify
# pip install --upgrade google-api-python-client

# How to get a Google API Key and OAuth2 credentials:
# 1) Go to https://console.developers.google.com
# 2) Create a project, eg. "JLM Video Captions"
# 3) Set the YouTube data API to "ON"
# 4) Create a public access key
# 5) Copy it to config/api-key.txt
# 6) Create an OAuth2 Client Id
# 7) Copy config/client-secrets.json.dist to config/client-secrets.json
# 8) Fill client_id and client_secret with your OAuth2 credentials

###############################################################################

import os
import re
import sys
import datetime
import dateutil.parser
import httplib2

from apiclient.discovery import build_from_document
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

from requests import get
from pprint import pprint
from colorama import init
from termcolor import colored, cprint
from slugify import slugify

# use Colorama to make Termcolor work on all platforms
init()

###############################################################################

CHANNEL_ID = "UCk-_PEY3iC6DIGJKuoEe9bw"  # JEAN-LUC MÉLENCHON

CAPTIONS_EXTENSION = 'sbv'  # or 'srt', but sbv looks better naked :)

CAPTIONS_DIRECTORY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'subtitles'
))

###############################################################################

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at
# {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client-secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
CLIENT_SECRETS_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'client-secrets.json'
))

# Grabbed from https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest
DISCOVERY_DOCUMENT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'youtube-v3-api-captions.json'
))

# Credentials created by the authentication process
OAUTH_CREDENTIALS = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'credentials-oauth2.json'
))

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
YOUTUBE_RW_SSL_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Message to display if the CLIENT_SECRETS_FILE is missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
ERROR: Please configure OAuth 2.0.

To download the captions you will need to populate the client_secrets.json file
found at:
   %s
with information from the APIs Console
https://console.developers.google.com

You can use config/client-secrets.json.dist as a template, but you'll need to
fill client_id and client_secret with your own OAuth2 credentials that you can
get from Google's API Console linked above.

For more information about the client-secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % CLIENT_SECRETS_FILE

###############################################################################

YOUTUBE_API_KEY_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'client-key.txt'
))

MISSING_API_KEY_FILE = """
ERROR : Api key missing.

How to get a Google API Key and OAuth2 credentials:
  1) Go to https://console.developers.google.com
  2) Create a project, eg. "JLM Video Captions"
  3) Set the YouTube data API to "ON"
  4) Create a public access key
  5) Copy it to %s
""" % YOUTUBE_API_KEY_FILE

YOUTUBE_API_KEY = ""
try:
    with open(YOUTUBE_API_KEY_FILE) as api_key_file:
        YOUTUBE_API_KEY = api_key_file.read().strip()
except IOError:
    cprint(MISSING_API_KEY_FILE, "red")
    exit(1)

###############################################################################


def get_authenticated_service(_args):
    """
    Authorize the request and store the authorization credentials.
    """
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
                                   scope=YOUTUBE_RW_SSL_SCOPE,
                                   message=MISSING_CLIENT_SECRETS_MESSAGE)

    storage = Storage(OAUTH_CREDENTIALS)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, _args)

    with open(DISCOVERY_DOCUMENT, "r") as f:
        doc = f.read()
        return build_from_document(
            doc, http=credentials.authorize(httplib2.Http())
        )

###############################################################################


def get_videos(page=None):
    url = 'https://www.googleapis.com/youtube/v3/search'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'channelId': CHANNEL_ID,
        'type': 'video',
        'part': 'snippet',
        'order': 'date',
        'maxResults': '50',  # 50 is the highest authorized value
    }

    if page is not None:
        parameters['pageToken'] = page

    response = get(url, params=parameters)

    if not response.ok:
        cprint("Request to Youtube API failed with response :", "red")
        print(response.text)

    return response.json()


def get_captions_for_video(video_id):
    url = 'https://www.googleapis.com/youtube/v3/captions'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'videoId': video_id,
        'part': 'snippet',
    }

    response = get(url, params=parameters)

    if not response.ok:
        cprint("Request to Youtube API failed with response :", "red")
        cprint(response.text, "red")

    return response.json()


# def get_caption(caption_id):
#     """
#     Does not work. We need OAuth2 for this.
#     Login Required - Response Code 401
#     """
#     url = "https://www.googleapis.com/youtube/v3/captions/%s" % caption_id
#     parameters = {
#         'key': YOUTUBE_API_KEY,
#         'id': caption_id,
#         'tfmt': 'sbv',
#     }
#
#     response = get(url, params=parameters)
#
#     if not response.ok:
#         cprint("Request to Youtube API failed with response :", "red")
#         cprint(response.text, "red")
#
#     return response


class Video:

    def __init__(self, yid, title, date):
        """
        :param yid: Youtube Id
        :param title: Unicode
        :param date: RFC 3339
        """
        self.yid = yid
        self.title = title
        self.date = dateutil.parser.parse(date)

    def __str__(self):
        return "%s - %s" % (self.yid, self.title)

    @property
    def slug(self):
        return slugify(self.title)


###############################################################################

if __name__ == "__main__":

    args = argparser.parse_args()

    cprint("Authenticating with YouTube...", "yellow")

    youtube = get_authenticated_service(args)

    print(
        colored("Collecting videos of channel ", "yellow") +
        colored(CHANNEL_ID, "magenta") +
        colored("...", "yellow")
    )


    def _parse_videos():
        for video_data in jsonResponse['items']:
            videos.append(Video(
                yid=video_data['id']['videoId'],
                title=video_data['snippet']['title'],
                date=video_data['snippet']['publishedAt']
            ))


    videos = []
    jsonResponse = get_videos()
    _parse_videos()
    while 'nextPageToken' in jsonResponse:
        nextPageToken = jsonResponse['nextPageToken']
        jsonResponse = get_videos(page=nextPageToken)
        _parse_videos()

    print("Found %s videos." % colored(str(len(videos)), "yellow"))

    cprint("Downloading captions from YouTube...", "yellow")

    captions_count = 0

    for video in videos:
        print("Retrieving captions for %s" % colored(video.title, "yellow"))
        jsonResponse = get_captions_for_video(video.yid)

        for caption_index, caption_data in enumerate(jsonResponse['items']):
            caption_kind = caption_data['snippet']['trackKind']
            if caption_kind != 'standard':
                print("  Ignored caption of kind %s." % caption_kind)
                continue
            if caption_data['snippet']['isDraft']:
                print("  Ignored caption draft.")
                continue

            caption_id = caption_data['id']
            caption_lang = caption_data['snippet']['language']
            caption_contents = youtube.captions().download(
                id=caption_id,
                tfmt=CAPTIONS_EXTENSION
            ).execute()
            caption_year = video.date.strftime("%Y")

            caption_filename = "%s.%s.%s.%s.%s" % (
                video.date.strftime("%Y-%m-%d"), video.slug,
                caption_lang, caption_id, CAPTIONS_EXTENSION
            )

            caption_path = os.path.join(
                CAPTIONS_DIRECTORY, caption_year, caption_filename
            )

            if not os.path.exists(os.path.dirname(caption_path)):
                os.makedirs(os.path.dirname(caption_path))
            with open(caption_path, mode="w") as caption_file:
                caption_file.write(caption_contents)

            captions_count += 1
            print("  Retrieved %s" % colored(caption_filename, "yellow"))

    print("Downloaded a grand total of %s captions."
          % colored(captions_count, "yellow"))

    cprint("Done!", "green")
