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
import argparse
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


def get_videos_of_channel(channel_id, page=None):
    url = 'https://www.googleapis.com/youtube/v3/search'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'channelId': channel_id,
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
        exit(1)

    return response.json()


def get_videos(video_ids):
    url = 'https://www.googleapis.com/youtube/v3/videos'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'id': ','.join(video_ids),
        'part': 'snippet',
        'maxResults': '50',
    }

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

    argparser = argparse.ArgumentParser(
        parents=[argparser], add_help=False,
        description="""
        A simple script to download all the published captions of all the
        videos of a channel from YouTube.
        It will ignore captions made with ASR (Automatic Speech Recognition).
        You need to set up `client-key.txt` and `client-secrets.json`
        in order to authenticate successfully with YouTube.
        """,
        epilog="""
        © WTFPL 2017 - YOU ARE FREE TO DO WHAT THE FORK YOU WANT
        """
    )

    argparser.add_argument(
        "--channel", default="UCk-_PEY3iC6DIGJKuoEe9bw",
        metavar="CHANNEL_ID",
        help="""
        Identifier of the YouTube channel publishing the videos for which the
        captions are to be downloaded.
        The default channel is the channel of "JEAN-LUC MÉLENCHON", which is
        the candidate of the INSOUMIS.
        This option is ignored if you provide the --videos option.
        """
    )

    argparser.add_argument(
        "--videos",
        nargs="+",
        metavar="VIDEO_ID",
        help="""
        Identifier(s) of the YouTube video(s) for which the captions are to be
        downloaded. When you provide this option, the script will only back up
        the captions of the specified video(s), and not of all the other videos
        of the channel, like it would normally do.
        Very useful to make a quick backup of only one or more video(s).
        You cannot provide more than 50 video ids to this parameter.
        Remember: YouTube's API has quotas, and using this option is the best
        way to not blow them.
        """
    )

    argparser.add_argument(
        "--extension", dest="extension", default="vtt",
        choices=['vtt', 'srt', 'sbv'],
        help="""
        File extension in which the captions will be downloaded.
        Available formats : srt for SubRip, sbv for SubViewer, vtt for WebVTT.
        The default is vtt.
        """
    )

    argparser.add_argument(
        "-?", "-h", "--help", dest="help", action="store_true",
        help="Display this documentation and exit."
    )

    args = argparser.parse_args()

    if args.help:
        argparser.print_help()
        argparser.exit(0)

    cprint("Authenticating with YouTube...", "yellow")

    youtube = get_authenticated_service(args)

    def _parse_videos(_videos, _json):
        for video_data in _json['items']:
            _id = video_data['id']
            if type(_id) is dict:
                _id = _id['videoId']
            _videos.append(Video(
                yid=_id,
                title=video_data['snippet']['title'],
                date=video_data['snippet']['publishedAt']
            ))

    def _s(int_or_list):
        if type(int_or_list) is list:
            int_or_list = len(int_or_list)
        return '' if int_or_list == 1 else 's'

    videos = []
    if args.videos:
        print(
            colored("Selecting video%s " % _s(args.videos), "yellow") +
            colored(', '.join(args.videos), "magenta") +
            colored("...", "yellow")
        )
        jsonResponse = get_videos(args.videos)
        if jsonResponse['pageInfo']['totalResults'] != len(args.videos):
            if len(args.videos) == 1:
                cprint("""
                Video %s probably do not exist.
                """ % args.videos[0], "red")
            else:
                cprint("""
                We could only retrieve %d out of the %d videos you provided.
                Either they don't exist, or you provided too many, because
                we do not support pagination here yet. Ask for it?
                """ % (
                    jsonResponse['pageInfo']['totalResults'], len(args.videos)
                ), "red")
            exit(1)
        _parse_videos(videos, jsonResponse)
    else:
        print(
            colored("Collecting videos of channel ", "yellow") +
            colored(args.channel, "magenta") +
            colored("...", "yellow")
        )

        jsonResponse = get_videos_of_channel(args.channel)
        _parse_videos(videos, jsonResponse)
        while 'nextPageToken' in jsonResponse:
            jsonResponse = get_videos_of_channel(
                args.channel, page=jsonResponse['nextPageToken']
            )
            _parse_videos(videos, jsonResponse)

    print("Found %s video%s." % (
        colored(str(len(videos)), "yellow"), _s(videos)
    ))

    cprint("Downloading captions from YouTube...", "yellow")

    captions_count = 0

    for video in videos:
        print("Retrieving captions for %s" % colored(video.title, "yellow"))
        jsonResponse = get_captions_for_video(video.yid)

        for caption_data in jsonResponse['items']:
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
                tfmt=args.extension
            ).execute().decode('utf-8')

            # YouTube writes comments on the first three lines of the VTT file:
            # WEBVTT
            # Kind: captions
            # Language: fr
            #
            # So we're going to append our metadata to these comments.
            if args.extension == 'vtt':
                caption_lines = caption_contents.split("\n")
                caption_contents_header = caption_lines[0:3]
                caption_contents_rest = caption_lines[3:]
                caption_contents_header.append(
                    "LastUpdated: %s" % caption_data['snippet']['lastUpdated']
                )
                caption_contents_header.append("Caption: %s" % caption_id)
                caption_contents_header.append("Video: %s" % video.yid)
                caption_contents = "\n".join(caption_contents_header) + "\n" \
                                   + "\n".join(caption_contents_rest)

            caption_filename = "%s.%s.%s.%s.%s" % (
                video.date.strftime("%Y-%m-%d"), video.slug,
                caption_lang, caption_id, args.extension
            )

            caption_year = video.date.strftime("%Y")
            caption_path = os.path.join(
                CAPTIONS_DIRECTORY, caption_year, caption_filename
            )

            if not os.path.exists(os.path.dirname(caption_path)):
                os.makedirs(os.path.dirname(caption_path))
            with open(caption_path, mode="w") as caption_file:
                caption_file.write(caption_contents.encode('utf-8'))

            captions_count += 1
            print("  Retrieved %s" % colored(caption_filename, "blue"))

    print("Downloaded a grand total of %s caption%s." % (
        colored(captions_count, "yellow"), _s(captions_count)
    ))

    cprint("Done!", "green")
