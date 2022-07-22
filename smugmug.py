"""
The bulk of this library was pulled (cloned) from marekrei/smuploader.git
    git clone https://github.com/marekrei/smuploader.git

It has been significantly modified to fit my specific purposes, including
including the ability to actually run under python 3.x

requirements.txt details the pip installable modules necessary for this project

Copywrite (C) 2022 Bitrox.io

"""

from rauth.service import OAuth1Service
import requests
import httplib2
import hashlib
import urllib
import time
import sys
import os
import json
import configparser
import re
import shutil


class SmugMug(object):
    smugmug_api_base_url = 'https://api.smugmug.com/api/v2'
    smugmug_upload_uri = 'http://upload.smugmug.com/'
    smugmug_request_token_uri = 'http://api.smugmug.com/services/oauth/1.0a/getRequestToken'
    smugmug_access_token_uri = 'http://api.smugmug.com/services/oauth/1.0a/getAccessToken'
    smugmug_authorize_uri = 'http://api.smugmug.com/services/oauth/1.0a/authorize'
    smugmug_api_version = 'v2'

    # put config in local directory under ./smugmug.ini
    smugmug_config = os.path.join(os.path.expanduser("."), 'config.ini')

    def __init__(self, verbose=False):
        """
        Constructor. 
        Loads the config file and initialises the smugmug service
        """

        self.verbose = verbose

        config_parser = configparser.RawConfigParser()
        config_parser.read(SmugMug.smugmug_config)
        try:
            self.username = config_parser.get('SMUGMUG', 'username')
            self.consumer_key = config_parser.get('SMUGMUG', 'consumer_key')
            self.consumer_secret = config_parser.get(
                'SMUGMUG', 'consumer_secret')
            self.access_token = config_parser.get('SMUGMUG', 'access_token')
            self.access_token_secret = config_parser.get(
                'SMUGMUG', 'access_token_secret')
        except:
            print('Missing config file, path: ',
                  SmugMug.smugmug_config, file=sys.stderr)
            raise Exception(
                "Config file is missing or corrupted. Run 'python smugmug.py'")

        self.smugmug_service = OAuth1Service(
            name='smugmug',
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            request_token_url=self.smugmug_request_token_uri,
            access_token_url=self.smugmug_access_token_uri,
            authorize_url=self.smugmug_authorize_uri)

        self.request_token, self.request_token_secret = self.smugmug_service.get_request_token(
            method='GET', params={'oauth_callback': 'oob'})
        self.smugmug_session = self.smugmug_service.get_session(
            (self.access_token, self.access_token_secret))
    """
    @staticmethod
    def decode(obj, encoding='utf-8'):
        if isinstance(obj, basestring):
            if not isinstance(obj, unicode):
                obj = unicode(obj, encoding)
        return obj
    """

    def get_authorize_url(self):
        """Returns the URL for OAuth authorisation"""
        self.request_token, self.request_token_secret = self.smugmug_service.get_request_token(
            method='GET', params={'oauth_callback': 'oob'})
        authorize_url = self.smugmug_service.get_authorize_url(
            self.request_token, Access='Full', Permissions='Add')
        return authorize_url

    def get_access_token(self, verifier):
        """Gets the access token from SmugMug"""
        self.access_token, self.access_token_secret = self.smugmug_service.get_access_token(method='POST',
                                                                                            request_token=self.request_token,
                                                                                            request_token_secret=self.request_token_secret,
                                                                                            params={'oauth_verifier': verifier})

        return self.access_token, self.access_token_secret

    def request_once(self, method, url, params={}, headers={}, files={}, data=None, header_auth=False):
        """Performs a single request"""
        if self.verbose == True:
            print('\nREQUEST:\nmethod='+method+'\nurl='+url +
                  '\nparams='+str(params)+'\nheaders='+str(headers))
            if len(str(data)) < 300:
                print("data="+str(data))

        response = self.smugmug_session.request(url=url,
                                                params=params,
                                                method=method,
                                                headers=headers,
                                                files=files,
                                                data=data,
                                                header_auth=header_auth)
        if self.verbose == True:
            print('RESPONSE DATA:\n' + str(response.content)[:2000] + (" ... " + str(
                response.content)[-2000:] if len(str(response.content)) > 2000 else ""))
        try:
            data = json.loads(response.content)
        except Exception:
            pass
        return data

    def request(self, method, url, params={}, headers={}, files={}, data=None, header_auth=False, retries=5, sleep=5):
        """Performs requests, with multiple attempts if needed"""
        retry_count = retries
        while retry_count > 0:
            try:
                response = self.request_once(
                    method, url, params, headers, files, data, header_auth)
                if ('Code' in response and response['Code'] in [200, 201]) or ("stat" in response and response["stat"] in ["ok"]):
                    return response
            except (requests.ConnectionError, requests.HTTPError, requests.URLRequired, requests.TooManyRedirects, requests.RequestException) as e:
                if self.verbose == True:
                    print(sys.exc_info()[0])
            if self.verbose == True:
                print('Retrying (' + str(retry_count) + ')...')
            time.sleep(sleep)
            retry_count -= 1
        print('Error: Too many retries, giving up.')
        sys.exit(1)

    # Album

    def get_albums(self, start=0, stepsize=100, pages=10000):
        """
        Get a list of all albums in the account
        """
        albums = []
        while(True and pages > 0):
            params = {'start': start, 'count': stepsize}
            response = self.request('GET', self.smugmug_api_base_url + "/user/"+self.username+"!albums",
                                    params=params, headers={'Accept': 'application/json', 'Cache-Control': 'no-cache'})

            for album in response['Response']['Album']:
                albums.append(
                    {"UrlPath": album["UrlPath"], "Title": album['Title'], "Uri": album["Uri"], "AlbumKey": album["AlbumKey"]})

            if 'NextPage' in response['Response']['Pages']:
                start += stepsize
                pages -= 1
            else:
                break
        return albums

    def get_album_names(self):
        """
        Return list of album names
        """
        albums = self.get_albums()
        album_names = [a["Title"] for a in albums]
        return album_names

    def get_album_id(self, album_name):
        """
        Get album id
        """
        if album_name == None:
            raise Exception("Album name needs to be defined")

        album_id = None
        for album in self.get_albums():
            title = album['Title']
            name = album_name
            # if SmugMug.decode(album['Title']) == SmugMug.decode(album_name):
            if title == name:
                album_id = album['AlbumKey']
                break
        return album_id

    def get_album_images(self, album_id, start=0, stepsize=500, pages=100000):
        """
        Get list of images in an album.
        """
        if album_id == None:
            raise Exception("Album ID must be set to retrieve images")

        images = []
        while(True and pages > 0):
            params = {'start': start, 'count': stepsize}
            response = self.request('GET', self.smugmug_api_base_url + "/album/" +
                                    album_id+"!images", params=params, headers={'Accept': 'application/json'})

            for image in (response['Response']['AlbumImage'] if 'AlbumImage' in response['Response'] else []):
                # Sample: /api/v2/image/mg4Xscx-1
                # image['ImageKey'] doesn't include the -1 suffix, which may change, so grab the full key
                # including the suffix from the image url so we can use it later
                image_key = image['Uris']['Image']['Uri'].split('/')[4]
                images.append({"ImageKey": image_key, "Uri": image["Uri"], "WebUri": image["WebUri"], "FileName": image["FileName"],
                              "ArchivedMD5": image["ArchivedMD5"], "ThumbnailUrl": image['ThumbnailUrl'], "OriginalSize": (image["OriginalSize"] if "OriginalSize" in image else None)})

            if 'NextPage' in response['Response']['Pages']:
                start += stepsize
                pages -= 1
            else:
                break
        return images

    def get_album_image_names(self, album_id):
        images = self.get_album_images(album_id)
        image_names = [i["FileName"] for i in images]
        return image_names

    def get_image_download_url(self, image_id):
        """
        Get the link for dowloading an image.
        """
        response = self.request('GET', self.smugmug_api_base_url + "/image/" +
                                image_id+"!download", headers={'Accept': 'application/json'})
        return response['Response']['ImageDownload']['Url']

    def get_image_core_info(self, image_id):
        """
        Get core info about a specific image
        """
        r = self.request('GET', self.smugmug_api_base_url+"/image/" +
                         image_id, headers={'Accept': 'application/json'})
        if r['Code'] == 200:
            return r['Response']['Image']
        else:
            return None

    def get_image_size_details(self, image_id):
        """
        Get the details associated with the available image sizes
        """
        r = self.request('GET', self.smugmug_api_base_url + "/image/" +
                         image_id+"!sizedetails", headers={'Accept': 'application/json'})
        return r['Response']['ImageSizeDetails']

    def create_nice_name(self, name):
        return "-".join([re.sub(r'[\W_]+', '', x) for x in name.strip().split()]).title()

    def create_album(self, album_name, password=None, folder_id=None, template_id=None):
        """
        Create a new album
        """
        data = {"Title": album_name, "NiceName": self.create_nice_name(
            album_name), 'OriginalSizes': 1, 'Filenames': 1}
        if password != None:
            data['Password'] = password

        if template_id != None:
            data["AlbumTemplateUri"] = template_id
            data["FolderUri"] = "/api/v2/folder/user/"+self.username + \
                ("/"+folder_id if folder_id != None else "")+"!albums"
            response = self.request('POST', self.smugmug_api_base_url + "/folder/user/"+self.username+("/"+folder_id if folder_id != None else "") +
                                    "!albumfromalbumtemplate", data=json.dumps(data), headers={'Accept': 'application/json', 'Content-Type': 'application/json'})
        else:
            response = self.request('POST', self.smugmug_api_base_url + "/folder/user/"+self.username + ("/"+folder_id if folder_id !=
                                    None else "") + "!albums", data=json.dumps(data), headers={'Accept': 'application/json', 'Content-Type': 'application/json'})

        if self.verbose == True:
            print(json.dumps(response))

        album_key = None
        if "Response" in response and "Album" in response["Response"] and "AlbumKey" in response["Response"]["Album"]:
            album_key = response["Response"]["Album"]["AlbumKey"]

        return response, album_key

    def get_album_info(self, album_id):
        """
        Get info for an album
        """
        response = self.request('GET', self.smugmug_api_base_url +
                                "/album/"+album_id, headers={'Accept': 'application/json'})
        return response["Response"]["Album"]

        album_info = dict()
        album_key = self.get_album_key(album_id)
        response = self.request('GET', self.smugmug_api_uri, params={
                                'method': 'smugmug.albums.getInfo', 'AlbumID': album_id, 'AlbumKey': album_key})
        info['album_id'] = response['Album']['id']
        info['album_name'] = response['Album']['Title']
        info['category_id'] = response['Album']['Category']['id']
        info['category_name'] = response['Album']['Category']['Name']
        return info

    def get_folders(self):
        """
        Get a list of folder names under the user.
        Currently supports only top-level folders.
        """
        response = self.request('GET', self.smugmug_api_base_url + "/folder/user/" +
                                self.username+"!folders", headers={'Accept': 'application/json'})
        folders = []
        for folder in response['Response']['Folder']:
            folders.append(
                {"Name": folder["Name"], "NodeID": folder["NodeID"], "UrlName": folder["UrlName"]})
        return folders

    def get_folder_names(self):
        """
        Return list of (top-level) folder names.
        """
        folders = self.get_folders()
        folder_names = [f["Name"] for f in folders]
        return folder_names

    def get_folder_id(self, folder_name):
        """
        Get category id
        """
        folder_id = None
        for folder in self.get_folders():
            if folder['Name'] == folder_name:
                folder_id = folder['UrlName']
                break
        return folder_id

    # Templates

    def get_templates(self):
        """
        Get a list of all album templates in the account
        """
        response = self.request('GET', self.smugmug_api_base_url + "/user/" +
                                self.username+"!albumtemplates", headers={'Accept': 'application/json'})
        templates = []
        for template in response['Response']['AlbumTemplate']:
            templates.append(
                {"Name": template['Name'], "Uri": template["Uri"]})
        return templates

    def get_template_names(self):
        """
        Return a list of template names.
        """
        templates = self.get_templates()
        template_names = [t["Name"] for t in templates]
        return template_names

    def get_template_id(self, template_name):
        """Get template id"""
        template_id = None
        for template in self.get_templates():
            if template['Name'] == template_name:
                template_id = template['Uri']
                break
        return template_id

    # Upload/download

    def upload_image(self, image_data, image_name, image_type, album_id):
        """Upload an image"""
        """Note that this requires a patched version of rauth to be installed as the standard OSS has a bug in session.py"""
        response = self.request('POST', self.smugmug_upload_uri,
                                data=image_data,
                                header_auth=True,
                                headers={'X-Smug-AlbumUri': "/api/v2/album/"+album_id,
                                         'X-Smug-Version': self.smugmug_api_version,
                                         'X-Smug-ResponseType': 'JSON',
                                         'Content-MD5': hashlib.md5(image_data).hexdigest(),
                                         'X-Smug-FileName': image_name,
                                         'Content-Length': str(len(image_data)),
                                         'Content-Type': image_type})
        return response

    def download_image(self, image_info, image_path, retries=5):
        """
        Download an image from a url
        """
        count = retries
        image_url = self.get_image_download_url(image_info["ImageKey"])
        image_path_temp = image_path + "_temp"

        while count > 0:
            count -= 1
            # Doing the actual downloading
            image_data = self.smugmug_session.request(
                url=image_url, method='GET', stream=True).raw
            image_data.decode_content = True
            with open(image_path_temp, 'wb') as f:
                shutil.copyfileobj(image_data, f)

            # Checking the image
            image_data_local = SmugMug.load_image(image_path_temp)
            image_md5sum = hashlib.md5(image_data_local).hexdigest()
            image_size = str(len(image_data_local))
            if image_md5sum != image_info['ArchivedMD5']:
                raise Exception("MD5 sum doesn't match.")
            elif image_info['OriginalSize'] is not None and image_size != str(image_info['OriginalSize']):
                raise Exception("Image size doesn't match.")
            else:
                os.rename(image_path_temp, image_path)
                break

            if count > 0:
                print("Retrying...")
            else:
                raise Exception("Error: Too many retries.")
                sys.exit(1)

    @staticmethod
    def load_image(image_path):
        """
        Load the image data from a path
        """
        try:
            image_data = open(image_path, 'rb').read()
            return image_data
        except IOError as e:
            raise "I/O error({0}): {1}".format(e.errno, e.strerror)
        return None
