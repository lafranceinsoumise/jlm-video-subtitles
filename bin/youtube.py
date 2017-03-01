#!/usr/bin/env python
# coding=utf-8

# The purpose of the script is to download all the subtitles files from Youtube
# Tested with python 2.7 only.

# I. Gather your tools.
#
# See setup.sh

# II. Pay a visit to the landlord of the forest, on your way there.
#
# How to get a Google API Key and OAuth2 credentials:
# 1) Go to https://console.developers.google.com
# 2) Create a project, eg. "JLM Video Captions"
# 3) Set the YouTube data API to "ON"
# 4) Create a public access key
# 5) Copy it to config/api-key.txt
# 6) Create an OAuth2 Client Id
# 7) Copy config/client-secrets.json.dist to config/client-secrets.json
# 8) Fill client_id and client_secret with your OAuth2 credentials

# III. Check the forest from afar
#
# bin/youtube.py --help

# IV. Do your gathering round
#
# bin/youtube.py

###############################################################################

import os
import re
import sys
import datetime
import dateutil.parser
import locale
import isodate
import strict_rfc3339
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
from github import Github, Requester

# use Colorama to make Termcolor work on all platforms
init()

THIS_DIRECTORY = os.path.abspath(os.path.dirname(__file__))


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
ERROR : Google API key missing.

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

GITHUB_API_KEY_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'config', 'github-key.txt'
))

MISSING_GITHUB_API_KEY_FILE = """
ERROR : Github API key missing.

How to get a Github API Key:
  1) Go to https://github.com/settings/tokens
  2) Create a new key
  3) Copy it to %s
""" % GITHUB_API_KEY_FILE

GITHUB_API_KEY = ""
try:
    with open(GITHUB_API_KEY_FILE) as api_key_file:
        GITHUB_API_KEY = api_key_file.read().strip()
except IOError:
    cprint(MISSING_GITHUB_API_KEY_FILE, "red")
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


def upload_caption(_youtube, _id, _file):
    return _youtube.captions().update(
        part="id",
        body=dict(
            id=_id
        ),
        media_body=_file,
        media_mime_type='test/vtt'
    ).execute()


###############################################################################

def parse_videos_from_json(_json):
    _videos = []
    for video_data in _json['items']:
        _id = video_data['id']
        if type(_id) is dict:
            _id = _id['videoId']
        _duration = None
        if 'contentDetails' in video_data:
            _duration = video_data['contentDetails']['duration']
        _videos.append(Video(
            yid=_id,
            title=video_data['snippet']['title'],
            date=video_data['snippet']['publishedAt'],
            duration=_duration
        ))
    return _videos


def get_latest_videos_of_channel(channel_id, cap=10, since_minutes_ago=120):
    assert cap < 51  # 50 is the highest authorized value in 2017
    t = datetime.datetime.now() - datetime.timedelta(minutes=since_minutes_ago)
    t = strict_rfc3339.timestamp_to_rfc3339_utcoffset(int(t.strftime("%s")))
    url = 'https://www.googleapis.com/youtube/v3/search'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'channelId': channel_id,
        'type': 'video',
        'part': 'snippet',
        'order': 'date',
        'publishedAfter': t,  # RFC 3339 with trailing Z, or it will not work
        'maxResults': '%d' % cap,
    }

    response = get(url, params=parameters)

    if not response.ok:
        cprint("Request to Youtube API failed with response :", "red")
        print(response.text)
        exit(1)

    return response.json()


def get_videos_of_channel(channel_id, page=None, cap=50):
    assert cap < 51  # 50 is the highest authorized value in 2017
    url = 'https://www.googleapis.com/youtube/v3/search'
    parameters = {
        'key': YOUTUBE_API_KEY,
        'channelId': channel_id,
        'type': 'video',
        'part': 'snippet',
        'order': 'date',
        'maxResults': '%d' % cap,
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
        'part': 'snippet,contentDetails',
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


###############################################################################

def _s(int_or_list):
    if type(int_or_list) is list:
        int_or_list = len(int_or_list)
    return '' if int_or_list == 1 else 's'


###############################################################################

def get_caption_file_by_id(_id, _dir, _ext):
    for dirpath, dirnames, filenames in os.walk(_dir):
        for name in filenames:
            if name.endswith(_ext):
                _caption = Caption.from_file(os.path.join(dirpath, name))
                _caption.filename = name
                if _caption.id == _id:
                    return _caption
    raise Exception("Found no caption for id %s" % _id)


# MODEL #######################################################################

class Video:

    def __init__(self, yid, title, date, duration=None):
        """
        :param yid: Youtube Id
        :param title: Unicode
        :param date: RFC 3339
        :param duration: ISO 8601 (PT prefix)
        """
        self.yid = yid
        self.title = title
        print("TITLE")
        pprint(title)
        print(type(title))
        self.date = dateutil.parser.parse(date)
        if duration is not None:
            self.duration = isodate.parse_duration(duration)
        else:
            self.duration = None

    def __str__(self):
        return "%s - %s" % (self.yid, self.title)

    @property
    def slug(self):
        return slugify(self.title)

    @property
    def day_fr(self):
        locale.setlocale(locale.LC_TIME, "fr_FR.utf8")
        day = self.date.strftime("%A %d %B %Y")
        locale.resetlocale(locale.LC_TIME)
        return day.capitalize().decode('utf-8')

    @property
    def day_en(self):
        locale.setlocale(locale.LC_TIME, "en_US.utf8")
        day = self.date.strftime("%A, %d %B %Y")
        locale.resetlocale(locale.LC_TIME)
        return day.decode('utf-8')

    @property
    def day_de(self):
        locale.setlocale(locale.LC_TIME, "de_DE.utf8")
        day = self.date.strftime("%A %d %B %Y")
        locale.resetlocale(locale.LC_TIME)
        return day.decode('utf-8')


class Caption:

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @staticmethod
    def from_file(filepath):
        metas = {}
        regex = re.compile("(\w+): +(.+)")
        with open(filepath, "r") as open_file:
            line = open_file.readline()
            while line and line.strip():  # stop at the first blank line
                line = open_file.readline()  # also, skip "WebVTT"
                matches = re.match(regex, line)
                if matches:
                    metas[matches.group(1).strip()] = matches.group(2).strip()

        return Caption(
            filepath=filepath,
            id=metas['Caption'],
            language=metas['Language'],
            modified_at=dateutil.parser.parse(metas['LastUpdated'])
        )

    @property
    def id(self):
        if not hasattr(self, 'id'):
            raise Exception("Caption without ID.")
        return self.id

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
        the candidate of the "Insoumis".
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
        "--captions",
        nargs="+",
        metavar="CAPTION_ID",
        help="""
        Identifier(s) of the YouTube caption(s) to upload to youtube.
        This option is only useful for the upload action.
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
        "--directory", dest="data_directory", default="../subtitles",
        help="""
        The directory where the captions are or where you want them to be.
        This is either an absolute path (when starting with /),
        or relative to the directory where this python script is : '%s'.
        """ % THIS_DIRECTORY
    )

    argparser.add_argument(
        "--repository", default="jlm2017/jlm-video-subtitles",
        metavar="OWNER/REPO",
        help="""
        Github repository in which to create issues during the 'github' action.
        """
    )

    argparser.add_argument(
        "--action", dest="action", default="help",
        choices=['help', 'download', 'upload', 'github'],
        help="""
        help : Show this help and exit.
        download : Download the caption files from youtube.\n
        upload : WIP\n
        github : Create relevant issues for each caption on github.
        """
    )

    argparser.add_argument(
        "-?", "-h", "--help", dest="help", action="store_true",
        help="Display this documentation and exit."
    )

    args = argparser.parse_args()

    if args.help or args.action == 'help':
        argparser.print_help()
        argparser.exit(0)

    if args.data_directory.startswith('/'):
        captions_directory = args.data_directory
    else:
        captions_directory = os.path.abspath(os.path.join(
            THIS_DIRECTORY, args.data_directory
        ))

    caption_extension = args.extension

    cprint("Authenticating with YouTube...", "yellow")

    youtube = get_authenticated_service(args)

    # ACTION = UPLOAD #########################################################

    if args.action == 'upload':
        raise NotImplementedError("Permissions required ! Work in progress...")

        # Logic
        # -----
        # check last publication date
        # fixme
        # if not different from stored
        # fixme
        # then actually upload
        if not args.captions:
            cprint("For the upload action,\n"
                   "You must provide caption(s) YouTube id(s) "
                   "in the --captions option.", "red")
            exit(1)

        caption_id = args.captions[0]

        caption = get_caption_file_by_id(caption_id, captions_directory, caption_extension)

        print("Uploading changes to caption %s"
              % colored(caption.filename, "yellow"))

        # googleapiclient.errors.HttpError: HttpError 403
        # when requesting
        # https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&alt=json&part=id
        # returned
        #   The permissions associated with the request are not sufficient
        #   to update the caption track.
        #   The request might not be properly authorized.
        #
        # fixme
        #
        # T_T

        upload_caption(youtube, caption.id, caption.filepath)

        cprint("Done!", "green")
        exit(0)

    # ACTION = GITHUB #########################################################

    # Create an issue on github for each new video.
    # - Video must not have an issue already
    # - Only check for videos published in the last 24h (for performance)

    if args.action == 'github':

        languages = [
            {
                'short': 'fr',
                'label': 'Language: French',
                'column': '398411',
                'issue': u"""
## {video.title}

&nbsp;          | Info
--------------- | ---------------
**Date**        | {video.day_fr}
**Durée**       | {video.duration} :clock7:
**Langue**      | Français :fr:
**Vidéo**       | [Voir dans YouTube :arrow_upper_right:](https://www.youtube.com/watch?v={video.yid})
**Sous-titres** | [Éditer dans YouTube :arrow_upper_right:](https://www.youtube.com/timedtext_editor?v={video.yid}&tab=captions&bl=vmp&action_mde_edit_form=1&lang=en&ui=hd)
"""
            }
            ,
            {
                'short': 'en',
                'label': 'Language: English',
                'column': '387590',
                'issue': u"""
## {video.title}

&nbsp;        | Info
------------- | -------------
**Date**      | {video.day_en}
**Duration**  | {video.duration} :clock7:
**Language**  | English :gb:
**Video**     | [See it on YouTube :arrow_upper_right:](https://www.youtube.com/watch?v={video.yid})
**Subtitles** | [Edit them in YouTube :arrow_upper_right:](https://www.youtube.com/timedtext_editor?v={video.yid}&tab=captions&bl=vmp&action_mde_edit_form=1&lang=en&ui=hd)
"""
            }
#             ,
#             {
#                 'short': 'de',
#                 'label': 'Language: German',
#                 'column': '654910',
#                 'issue': u"""
# Titel | {video.title}
# ----- | -----
# Dauer | {video.duration}
# Sprache | German
# Verweise | [VIDEO](https://www.youtube.com/watch?v={video.yid}) - [EDITOR](https://www.youtube.com/timedtext_editor?v={video.yid}&tab=captions&bl=vmp&action_mde_edit_form=1&lang=en&ui=hd)
# """
#             }
        ]

        print("Collecting issues of repository %s..."
              % colored(args.repository, "yellow"))

        gh = Github(GITHUB_API_KEY)
        repo = gh.get_repo(args.repository)

        # The Projects API is still in development
        # - https://developer.github.com/v3/projects
        # - It's not supported by the python lib yet
        # - We need to provide a special "Accept" header
        # So, we hack in our own support ; it's dirty but it works.
        # Be warned : it may break at any moment -_-
        GITHUB_ACCEPT = "application/vnd.github.inertia-preview+json"
        rq = Requester.Requester(
            GITHUB_API_KEY, None, "https://api.github.com", 10, None, None,
            'PyGithub/Python', 30, False
        )

        # Useful to get the IDs of the Projects
        # headers, data = rq.requestJsonAndCheck(
        #     "GET",
        #     "/repos/%s/projects" % args.repository,
        #     None,
        #     {"Accept": GITHUB_ACCEPT}
        # )
        # pprint(data)

        # Useful to get the IDs of the Columns
        # headers, data = rq.requestJsonAndCheck(
        #     "GET",
        #     "/projects/%s/columns" % '373399',
        #     None,
        #     {"Accept": GITHUB_ACCEPT}
        # )
        # pprint(data)

        # List cards of a Column
        # headers, data = rq.requestJsonAndCheck(
        #     "GET",
        #     "/projects/columns/%s/cards" % '398411',
        #     None,
        #     {"Accept": GITHUB_ACCEPT}
        # )
        # pprint(data)

        issues = repo.get_issues()

        labels = {}
        for language in languages:
            labels[language['short']] = repo.get_label(language['label'])
        label_start = repo.get_label('Process: [0] Awaiting subtitles')

        if args.videos:
            print(
                colored("Selecting video%s " % _s(args.videos), "yellow") +
                colored(', '.join(args.videos), "magenta") +
                colored("...", "yellow")
            )
            ids = args.videos
        else:
            print("Collecting latest videos of channel %s..."
                  % colored(args.channel, "yellow"))
            jsonResponse = get_latest_videos_of_channel(args.channel)
            videos = parse_videos_from_json(jsonResponse)
            ids = [video.yid for video in videos]

        jsonResponse = get_videos(ids)
        videos = parse_videos_from_json(jsonResponse)

        for video in videos:
            for language in languages:
                issue_title = "[subtitles] [%s] %s" % \
                              (language['short'], video.title)

                print("Looking for issue %s..."
                      % colored(issue_title, "yellow"))

                found = False
                for issue in issues:
                    if issue.title == issue_title:
                        found = True
                        break
                if found:
                    print("  Found existing issue. Skipping...")
                else:
                    print("  Issue not found. Creating it now...")
                    issue_body = language['issue'].format(video=video)
                    issue = repo.create_issue(
                        issue_title,
                        body=issue_body,
                        labels=[labels[language['short']], label_start]
                    )
                    # Ok, this is a total hack that may break at any point,
                    # because the Cards API is a dev-preview only.
                    print("  Creating a card for it as well...")
                    headers, data = rq.requestJsonAndCheck(
                        verb="POST",
                        url="/projects/columns/%s/cards" % language['column'],
                        input={
                            'content_id': issue.id,
                            'content_type': 'Issue'
                        },
                        headers={"Accept": GITHUB_ACCEPT}
                    )

        if 0 == len(videos):
            print("No recent videos were found.")

        cprint("Done!", "green")
        exit(0)

    # ACTION = DOWNLOAD #######################################################

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
        videos.extend(parse_videos_from_json(jsonResponse))
    else:
        print(
            colored("Collecting videos of channel ", "yellow") +
            colored(args.channel, "magenta") +
            colored("...", "yellow")
        )

        jsonResponse = get_videos_of_channel(args.channel)
        videos.extend(parse_videos_from_json(jsonResponse))
        while 'nextPageToken' in jsonResponse:
            jsonResponse = get_videos_of_channel(
                args.channel, page=jsonResponse['nextPageToken']
            )
            videos.extend(parse_videos_from_json(jsonResponse))

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
                tfmt=caption_extension
            ).execute().decode('utf-8')

            # YouTube writes comments on the first three lines of the VTT file:
            # WEBVTT
            # Kind: captions
            # Language: fr
            #
            # So we're going to append our metadata to these comments.
            if caption_extension == 'vtt':
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
                caption_lang, caption_id, caption_extension
            )

            caption_year = video.date.strftime("%Y")
            caption_path = os.path.join(
                captions_directory, caption_year, caption_filename
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
    exit(0)
