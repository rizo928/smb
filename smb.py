#!/usr/bin/env python3

"""
This program is intended to provide a quick and easy way for bloggers to
upload images to smugmug albums and then grab image URIs, including
those suitable for embedding of various sizes.

This program was born out of the fact that the smugmug mobile app
takes FOREVER to autoupload images from iOS.  It also doesn't provide
any way whatsoever to get the URI for various sizes of an image.

While one could aways use the full smugmug.com site and associated
smugmug organizer to do everything this app does, it's much MUCH slower
to do so.

Ok...and lets be honest, this app is really just us having fun coding something
interesting that is mildly useful :-)

requirements.txt details the pip installable modules necessary for this project

This program depends on a highly modified version of marekrei/smuploader.git
    git clone https://github.com/marekrei/smuploader.git
See smugmug.py for details

Copywrite (C) 2022 Bitrox.io

"""

# from pip imported libraries
from flask import Flask, flash, redirect, url_for, render_template, request, session, abort
from flask_session import Session  # flask-session
from werkzeug.utils import secure_filename  # included w/ flask
import httpagentparser
import configparser

from smugmug import *  # local file

from urllib.parse import urlparse, parse_qs
from glob import glob
import json
import sys
import os
import collections.abc

app = Flask(__name__, static_url_path='',
            static_folder='static',
            template_folder='templates')
app.config['UPLOAD_FOLDER'] = "static/upload"

# path to config file
smb_config = os.path.join(os.path.expanduser("."), 'config.ini')
config_parser = configparser.RawConfigParser()
config_parser.read(smb_config)

disable_login = False
ux_g = {}
ux_g["app_name"] = "SM Access v0.9"

try:
    app.config['ENV'] = 'production'
    app.config["DEBUG"] = False  # config_parser.get('SMB', 'debug')
    app.config["SECRET_KEY"] = config_parser.get('SMB', 'session_key')
    user_id = config_parser.get('SMB', 'user_id')
    user_pswd = config_parser.get('SMB', 'user_pswd')
    if config_parser.get('SMB', 'disable_login') == 'True':
        disable_login = True

    # load any global variables to be passed to all calls to render_template
    ux_g["album1_name"] = config_parser.get('SMB', 'album1_name')
    ux_g["album1_id"] = config_parser.get('SMB', 'album1_id')
    ux_g["album2_name"] = config_parser.get('SMB', 'album2_name')
    ux_g["album2_id"] = config_parser.get('SMB', 'album2_id')
    ux_g["album3_name"] = config_parser.get('SMB', 'album3_name')
    ux_g["album3_id"] = config_parser.get('SMB', 'album3_id')
    ux_g["userid"] = "Anonymous"  # set at login
    upload_path = config_parser.get('SMB', 'upload_path')
    if upload_path == None:
        upload_path = "."
    download_path = config_parser.get('SMB', 'download_path')
    if download_path == None:
        download_path = "."

except:
    print('Missing config file, path: ', smb_config, file=sys.stderr)
    raise Exception("Config file is missing or corrupted.")

# Check for needed subdirectories and try to create if they don't exist
mode = 0o744
if not os.path.isdir(upload_path):
    print('Upload path does not exist, will try to creat it: ',
          upload_path, file=sys.stderr)
    try:
        os.mkdir(upload_path, mode)
    except:
        print('Exception creating upload path, exiting.', file=sys.stderr)
        print('Check your config.ini for upload_path definition.', file=sys.stderr)
        quit()
    else:
        print('Successfully created upload directory.', file=sys.stderr)

if not os.path.isdir(download_path):
    print('Download path does not exist, will try to creat it: ',
          download_path, file=sys.stderr)
    try:
        os.mkdir(download_path, mode)
    except:
        print('Exception creating download path, exiting', file=sys.stderr)
        print('Check your config.ini for download_path definition.', file=sys.stderr)
        quit()
    else:
        print('Successfully created download directory.', file=sys.stderr)

# app.config["DEBUG"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)  # setup server side session from app

sm = SmugMug()


class dict2obj:
    # constructor
    def __init__(self, dict1):
        self.__dict__.update(dict1)


def is_ios():
    uap = httpagentparser.detect(request.user_agent.string)
    # print('User agent detect: ', uap, file=sys.stderr)
    if uap['os']['name'] == 'iOS':
        print('iPhone detected!', file=sys.stderr)
        return True
    else:
        return False


def status_msg(the_msg):
    # allows returning either an array of status messages or a single status message
    if hasattr(the_msg, '__len__') and (not isinstance(the_msg, str)):
        return render_template('status.html', status_msg=the_msg, ux_g=ux_g)
    return render_template('status.html', status_msg=[the_msg], ux_g=ux_g)


@app.route("/test")
def test():
    theArgs = {"album1_name": "album1", "album1_id": "1-id",
               "album2_name": "album2", "album2_id": "2-id"}
    return render_template('test.html', ux_g=ux_g)


@app.route("/login", methods=["POST", "GET"])
def login():
    if disable_login == True:
        print('Login Disabled', file=sys.stderr)
        session["userid"] = 'Anonymous'
        return redirect("/")
    else:
        print('Login Enabled', file=sys.stderr)

    if request.method == "POST":
        # record the user name
        if request.form.get("userid") != user_id:
            print('Unknown user id', file=sys.stderr)
            return render_template('login.html', statusmsg='Unknown credentials', ux_g=ux_g)
        if request.form.get("pswd") != user_pswd:
            print('Unknown user password', file=sys.stderr)
            return render_template('login.html', statusmsg='Unknown credentials', ux_g=ux_g)
        session["userid"] = request.form.get("userid")
        ux_g["userid"] = session["userid"]
        # redirect to the main page
        return redirect("/")
    return render_template('login.html', ux_g=ux_g)


@app.route("/logout")
def logout():
    session["userid"] = None
    ux_g["userid"] = "Anonymous"
    return redirect("/login")


@app.route("/")
def home():
    if not session.get("userid"):
        return redirect("/login")
    return render_template('home.html', ux_g=ux_g)


@app.route("/albums")
def albums():
    if not session.get("userid"):
        return redirect("/login")

    albums = sm.get_albums()
    sorted_albums = sorted(albums, key=lambda d: d['UrlPath'], reverse=True)
    return render_template('albums.html', len=len(albums), albums=sorted_albums, ux_g=ux_g)


@app.route("/images")
def images():
    if not session.get("userid"):
        return redirect("/login")

    skip_images = request.args.get('noimages')
    album_id = request.args.get('album_id')
    if album_id == None:
        print('Missing albumID', file=sys.stderr)
        return status_msg("Missing album_id parameter in /images")

    # setup paging variables (start = start page, stepsize = # of images/page, pages = # of pages)
    sStart = request.args.get('start')
    if sStart == None:
        start = 0
    else:
        start = int(sStart)
    sPages = request.args.get('pages')
    if sPages == None:
        pages = 10000
    else:
        pages = int(sPages)
    sStepSize = request.args.get('stepsize')
    if sStepSize == None:
        stepsize = 100
    else:
        stepsize = int(sStepSize)

    # get_album_images(self, album_id, start=0, stepsize = 500, pages = 100000)
    images = sm.get_album_images(
        album_id, start=start, stepsize=stepsize, pages=pages)
    # We really want to return images in the order they're in within the gallery
    # sorted_images = sorted(images, key=lambda d: d['FileName'], reverse=False)

    if skip_images != None:  # parameter vs. header check
        return render_template('images-ios.html', len=len(images), images=images, ux_g=ux_g)
    else:
        return render_template('images.html', len=len(images), images=images, ux_g=ux_g)


@app.route("/findimage")
def findimage():
    if not session.get("userid"):
        return redirect("/login")

    album_id = request.args.get('album_id')
    search_str = request.args.get('searchstr')
    skip_images = request.args.get('noimages')
    if album_id == None:
        print('Missing albumID', file=sys.stderr)
        return status_msg("Missing albumID parameter for /findimage")
    if search_str == None:
        print('Missing search_str', file=sys.stderr)
        return status_msg("Missing searchstr parameter for /findimage")

    # print('Searching for image in album id: ', album_id, file=sys.stderr)
    # print('Searching for: ', search_str, file=sys.stderr)

    images = sm.get_album_images(album_id)
    # sorted_images = sorted(images, key=lambda d: d['FileName'], reverse=False)
    found_image = False
    for image in images:
        if (image['FileName'].find(search_str) != -1):
            found_image = True
            break
    if found_image:
        """
        images.append({"ImageKey": image_key, "Uri": image["Uri"], "FileName": image["FileName"],
        "ArchivedMD5": image["ArchivedMD5"], "ThumbnailUrl": image['ThumbnailUrl'], "OriginalSize": (image["OriginalSize"] if "OriginalSize" in image else None)})
        """
        image_id = image['ImageKey']
        image_core_info = sm.get_image_core_info(image_id)
        image_size_details = sm.get_image_size_details(image_id)
        if image_core_info != None:
            image_info = {}
            image_info['ImageKey'] = image_core_info['ImageKey']
            image_info['FileName'] = image_core_info['FileName']
            image_info['ArchivedSize'] = image_core_info['ArchivedSize']
            image_info['ArchivedMD5'] = image_core_info['ArchivedMD5']
            image_info['OriginalSize'] = image_core_info['OriginalSize']
        return render_template('image.html', image_size_details=image_size_details, image_info=image_info, ux_g=ux_g)
    else:
        return status_msg("Unable to find an image matching that string")


@app.route("/image")
def image():
    """ Get a specific image specified by image_id parameter """

    if not session.get("userid"):
        return redirect("/login")

    image_id = request.args.get('image_id')
    print('Received image id: ', image_id, file=sys.stderr)
    if image_id == None:
        print('Missing image_id', file=sys.stderr)
        return status_msg("Missing image_id parameter for /image")

    image_core_info = sm.get_image_core_info(image_id)
    image_size_details = sm.get_image_size_details(image_id)
    if image_core_info != None:
        image_info = {}
        image_info['ImageKey'] = image_core_info['ImageKey']
        image_info['FileName'] = image_core_info['FileName']
        image_info['ArchivedSize'] = image_core_info['ArchivedSize']
        image_info['ArchivedMD5'] = image_core_info['ArchivedMD5']
        if 'OriginalSize' in image_core_info:
            image_info['OriginalSize'] = image_core_info['OriginalSize']
        else:
            image_info['OriginalSize'] = 0

        return render_template('image.html', image_size_details=image_size_details, image_info=image_info, ux_g=ux_g)
    else:
        print('Unsuccessful attempt to retrieve image core info', file=sys.stderr)
        return status_msg("Unsuccessful attempt to retrieve image core info")


@app.route("/pick")
def pick():
    if not session.get("userid"):
        return redirect("/login")
    aidx = request.args.get('albumidx')
    if aidx == None:
        return status_msg("Missing album_num in /pick")
    # print('album_num: ',aidx, file=sys.stderr)
    if int(aidx) < 1 or int(aidx) > 3:
        return status_msg("Valid album_num not passed to /pick: "+aidx)
    an_key = 'album'+str(aidx)+'_name'
    ai_key = 'album'+str(aidx)+'_id'
    print('Ask user to take/pick an image to upload for ',
          an_key+':'+ai_key, file=sys.stderr)
    return render_template('pick.html', ux_g=ux_g, album_name=ux_g[an_key], album_id=ux_g[ai_key])


@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("userid"):
        return redirect("/login")

    album_id = request.args.get('album_id')
    if album_id == None:
        return status_msg("Missing album_id in /upload")

    print('Album ID: ', album_id, file=sys.stderr)

    # get the list from the files object
    f_list = request.files.getlist("images")
    print('Images: ', f_list, file=sys.stderr)
    smg = []
    counter = 0
    for f in f_list:
        counter += 1
        file_name = secure_filename(f.filename)
        file_name = os.path.join(upload_path, file_name)
        print('Full local server upload path: ', file_name, file=sys.stderr)
        # return status_msg("Check console for full upload path")
        try:
            f.save(file_name)
        except:
            return status_msg("Unable to upload image to local server.")
        else:
            print('Successfully saved image locally on server', file=sys.stderr)

        image_data = sm.load_image(file_name)  # read it back in from the disk
        upload_response = sm.upload_image(
            image_data=image_data, image_name=file_name, image_type=f.mimetype, album_id=album_id)
        smg.append(file_name +
                   " upload status: " + upload_response["stat"])

# Upload json response
# {
#   "Asset":{
#       "AssetComponentUri":"/api/v2/library/asset/nqtF7w2/component/i/n1808w2",
#   "AssetUri":"/api/v2/library/asset/nq328w2"
#   },
#   {
#   "Image":{
#       "AlbumImageUri":"/api/v2/album/2cwFNh/image/nqZbBw4-0",
#       "ImageUri":"/api/v2/image/nQtSB32-0",
#       "StatusImageReplaceUri":"",
#       "URL":"https://my.customdomain.io/Blogs/TestBlog/n-456bmF/i-n323w2"
#   },
#   "method":"smugmug.images.upload",
#   "stat":"ok"
# }

    return status_msg(smg)


@app.route("/download")
def download():
    if not session.get("userid"):
        return redirect("/login")

    image_info = {"ImageKey": "nQtF532",
                  "ArchivedMD5": "9682cc419980e7c3b72758d9b6bda989", "OriginalSize": "1529569"}
    image_path = "downloaded.jpg"
    print('Downloading image...', file=sys.stderr)
    response = sm.download_image(image_info, image_path, retries=2)
    return status_msg('Downloaded image from Test Blog')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
