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
from distutils.log import info
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
import logging
import collections.abc

app = Flask(__name__, static_url_path='',
            static_folder='static',
            template_folder='templates')
app.config['UPLOAD_FOLDER'] = "static/upload"

# Unless you set the logger basic configuration, no log message is sent
# with level INFO or lower regardless of what setLevel() is set to
logging.basicConfig(level=logging.WARNING)
app.logger.setLevel("INFO")

# path to config file
smb_config = os.path.join(os.path.expanduser("."), 'config.ini')
# config = configparser.RawConfigParser()
config = configparser.ConfigParser()
config.read(smb_config)

disable_login = False
ux_g = {}
ux_g["app_name"] = "SMB v0.02"
user_id = "anonymous"
user_pswd = ""
user_pswd = None

try:
    app.config['ENV'] = 'development'
    app.config["DEBUG"] = True  # config.get('SMB', 'debug')
    app.config["SECRET_KEY"] = config.get('SMB', 'session_key')
    user_id = config.get('SMB', 'user_id')
    user_pswd = config.get('SMB', 'user_pswd')
    if config.get('SMB', 'disable_login') == 'True':
        disable_login = True

    # load any global variables to be passed to all calls to render_template
    ux_g["album1_name"] = config.get('SMB', 'album1_name')
    ux_g["album1_id"] = config.get('SMB', 'album1_id')
    ux_g["album2_name"] = config.get('SMB', 'album2_name')
    ux_g["album2_id"] = config.get('SMB', 'album2_id')
    ux_g["album3_name"] = config.get('SMB', 'album3_name')
    ux_g["album3_id"] = config.get('SMB', 'album3_id')
    ux_g["userid"] = "Anonymous"  # set at login
    upload_path = config.get('SMB', 'upload_path')
    if upload_path == None:
        upload_path = "."
    download_path = config.get('SMB', 'download_path')
    if download_path == None:
        download_path = "."

except:
    app.logger.warning('Missing config file, path: ', smb_config)
    raise Exception("Config file is missing or corrupted.")

# Check for needed subdirectories and try to create if they don't exist
mode = 0o744
if not os.path.isdir(upload_path):
    app.logger.warning('Upload path does not exist, will try to creat it: %s',
          upload_path)
    try:
        os.mkdir(upload_path, mode)
    except:
        app.logger.error('Exception creating upload path, exiting.')
        app.logger.error('Check your config.ini for upload_path definition.')
        quit()
    else:
        app.logger.info('Successfully created upload directory.')

if not os.path.isdir(download_path):
    app.logger.warning('Download path does not exist, will try to creat it: %s',
          download_path)
    try:
        os.mkdir(download_path, mode)
    except:
        app.logger.error('Exception creating download path, exiting')
        app.logger.error('Check your config.ini for download_path definition.')
        quit()
    else:
        app.logger.info('Successfully created download directory.')

# app.config["DEBUG"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)  # setup server side session from app

sm = SmugMug()

class dict2obj:
    # constructor
    def __init__(self, dict1):
        self.__dict__.update(dict1)

# This isn't really used, but it's hear in case one would like to operate
# differently depending on whether or not we're dealing with iOS device
def is_ios():
    uap = httpagentparser.detect(request.user_agent.string)
    # print('User agent detect: ', uap)
    if uap['os']['name'] == 'iOS':
        app.logger.info('iPhone detected!')
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
        app.logger.warning('Login Disabled')
        session["userid"] = 'Anonymous'
        return redirect("/")
    else:
        app.logger.info('Login Enabled')
        if not session["userid"] == None:
            # already logged in, just go to the home page
            return redirect("/")

    if request.method == "POST":
        entered_id = request.form.get("userid")
        entered_pwd = request.form.get("pswd")

        if not entered_id.isidentifier():
            app.logger.warning('Invalid login id entered')
            return render_template('login.html', ux_g=ux_g)
        if entered_id != user_id:
            app.logger.warning('Unknown user id: '+entered_id+" : "+user_id)
            return render_template('login.html', status_msg='Unknown credentials', ux_g=ux_g)

        if not entered_pwd.isidentifier():
            app.logger.warning('Invalid password entered')
            return render_template('login.html', ux_g=ux_g)
        if entered_pwd != user_pswd:
            app.logger.warning('Unknown user password')
            return render_template('login.html', status_msg='Unknown credentials', ux_g=ux_g)
        session["userid"] = entered_id
        ux_g["userid"] = entered_id
        # redirect to the main page
        return redirect("/")
    return render_template('login.html', ux_g=ux_g)


@app.route("/logout")
def logout():
    session["userid"] = None
    ux_g["userid"] = "Anonymous"
    return redirect("/login")

@app.route("/credentials", methods=["POST", "GET"])
def credentials():
    global ux_g, user_id, user_pswd, config, smb_config
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    if request.method == "POST":
        valid_credentials = True
        if not request.form.get("loginID").isidentifier():
            app.logger.warning('Invalid login id entered')
            valid_credentials = False
            # return render_template('login.html', statusmsg='Unknown credentials', ux_g=ux_g)
        if not request.form.get("pswd").isidentifier():
            app.logger.warning('Invalid password entered')
            valid_credentials = False
            # return render_template('login.html', statusmsg='Unknown credentials', ux_g=ux_g)
        if not valid_credentials:
            app.logger.warning('Invalid credentials entered')
            return render_template('credentials.html', status_msg='Invalid credentials submitted', ux_g=ux_g)            

        # session["userid"] = request.form.get("userid")
        # ux_g["userid"] = session["userid"]
        # redirect to the main page

        try:

            config['SMB']['user_id'] = request.form.get("loginID")
            config['SMB']['user_pswd'] = request.form.get("pswd")
            with open(smb_config, 'w') as configfile:    # save
                config.write(configfile)
            app.logger.info('Valid credentials entered and successfully updated')
            user_id = request.form.get("loginID")
            user_pswd = request.form.get("pswd")
            session["userid"] = user_id
            ux_g["userid"] = user_id

            return status_msg('Login credentials successfully updated')
        except:
            app.logger.error('Error attempting to write credentials to config file.')
            return status_msg('Error attempting to write credentials to config file, credentials unchanged!')
    
    return render_template('credentials.html', status_msg='', ux_g=ux_g)

@app.route("/")
def home():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")
    return render_template('home.html', ux_g=ux_g)


@app.route("/albums")
def albums():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    albums = sm.get_albums()
    sorted_albums = sorted(albums, key=lambda d: d['UrlPath'], reverse=True)
    return render_template('albums.html', len=len(albums), albums=sorted_albums, ux_g=ux_g)


@app.route("/images")
def images():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    skip_images = request.args.get('noimages')
    album_id = request.args.get('album_id')
    if album_id == None:
        app.logger.warning('Missing albumID')
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
        return render_template('images-list.html', len=len(images), images=images, ux_g=ux_g)
    else:
        return render_template('images.html', len=len(images), images=images, ux_g=ux_g)


@app.route("/findimage")
def findimage():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    album_id = request.args.get('album_id')
    search_str = request.args.get('searchstr')
    skip_images = request.args.get('noimages')
    if album_id == None:
        app.logger.warning('Missing albumID')
        return status_msg("Missing albumID parameter for /findimage")
    if search_str == None:
        app.logger.warning('Missing search_str')
        return status_msg("Missing searchstr parameter for /findimage")

    # print('Searching for image in album id: ', album_id)
    # print('Searching for: ', search_str)

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
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    image_id = request.args.get('image_id')
    app.logger.info('Received image id: %s', image_id)
    if image_id == None:
        app.logger.warning('Missing image_id')
        return status_msg("Missing image_id parameter for /image")

    image_core_info = sm.get_image_core_info(image_id)
    image_size_details = sm.get_image_size_details(image_id)
    image_sizes = list(reversed(image_size_details['UsableSizes']))
        # We want the bigger sizes first in the list to avoid unnecessary scrolling
        # since modern blogs tend to use bigger image sizes
    app.logger.info('Image size key array: %s', image_sizes)
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

        return render_template('image.html', image_sizes=image_sizes, image_size_details=image_size_details, image_info=image_info, ux_g=ux_g)
    else:
        app.logger.error('Unsuccessful attempt to retrieve image core info')
        return status_msg("Unsuccessful attempt to retrieve image core info")


@app.route("/pick")
def pick():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")
    aidx = request.args.get('albumidx')
    if aidx == None:
        return status_msg("Missing album_num in /pick")
    # print('album_num: ',aidx)
    if int(aidx) < 1 or int(aidx) > 3:
        return status_msg("Valid album_num not passed to /pick: "+aidx)
    an_key = 'album'+str(aidx)+'_name'
    ai_key = 'album'+str(aidx)+'_id'
    app.logger.info('Ask user to take/pick an image to upload for %s', an_key+':'+ai_key)
    return render_template('pick.html', ux_g=ux_g, album_name=ux_g[an_key], album_id=ux_g[ai_key]) # pick


@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    album_id = request.args.get('album_id')
    if album_id == None:
        return status_msg("Missing album_id in /upload")

    app.logger.info('Album ID: %s', album_id)

    # get the list from the files object
    f_list = request.files.getlist("images")
    app.logger.info('Images: %s', f_list)
    smg = []
    counter = 0
    for f in f_list:
        counter += 1
        file_name = secure_filename(f.filename)
        file_name = os.path.join(upload_path, file_name)
        app.logger.info('Full local server upload path: %s', file_name)
        # return status_msg("Check console for full upload path")
        try:
            f.save(file_name)
        except:
            return status_msg("Unable to upload image to local server.")
        else:
            app.logger.info('Successfully saved image locally on server')

        image_data = sm.load_image(file_name)  # read it back in from the disk
        upload_response = sm.upload_image(
            image_data=image_data, image_name=file_name, image_type=f.mimetype, album_id=album_id)
        smg.append(file_name +
                   " upload status: " + upload_response["stat"])

    return status_msg(smg) # upload


@app.route("/download")
def download():
    if not session.get("userid"):
        ux_g["userid"] = "Anonymous"
        return redirect("/login")

    image_info = {"ImageKey": "nQtF532",
                  "ArchivedMD5": "9682cc419980e7c3b72758d9b6bda989", "OriginalSize": "1529569"}
    image_path = "downloaded.jpg"
    app.logger.info('Downloading image...')
    response = sm.download_image(image_info, image_path, retries=2)
    return status_msg('Downloaded image from Test Blog') # download

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
