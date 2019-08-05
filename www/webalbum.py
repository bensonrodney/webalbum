#!/usr/bin/python

"""
The idea behind this web album is to reduce the effort required to keep web ablum up to date with
source images that make up the web album.

For me, every time I took some new photos and copied them to my web server I would have to
run some web album generator which would take forever, mostly due to my 60,000+ photos in my
personal digital photo album. Having so many photos is the reason I use a web album to browse
through them.

This cgi based web album is designed to generate each directory view or image view page as it
is requested. This means there is no maintenance required when there are more images added to
the source image collection.

Firstly, I hacked this together fairly quickly and over time added some bits and pieces to make
viewing easier (like the previous/next directory links at the top AND the bottom of directory
view pages).

Because I used minimal time to get this up and running, I've made no effort to make this work
on platforms other than Ubuntu. It may work on other platforms but I wouldn't bank on it.

There are some things that need to be configured. There are a couple of ways:
  - use a configuration file (config parameter retrieval function is included)
  - just hard code the config items into this file and leave it at that
Either of these two config methods would allow you to run more than one web album, each
pointing to different image collections.

I'm using this webalbum on Ubuntu with Apache as the web server. Below is how I configured it.
You might need to fill in the blanks for some points that I've glossed over too quickly, the point
here is to explain this webalbum.

1. Set up your web server and enable cgi - a good guide for doing this with Apache
     is here http://httpd.apache.org/docs/2.2/howto/cgi.html

2. Make sure the original images are can be viewed on your web server under some directory
     on webserver, eg http://www.mydomain.org/photos/originals/somedir/some_image.jpg
     In this example /photos/originals/ is the root directory of the original images on
     the webserver

3. Set config items in the code below:

     ALBUM_ROOT: this is the local path to the original photos. This is the actual path, not a
         path relative to the web server's root, eg /mnt/some_mount_point/image_store
         In this example, along with the example in point 2,
             /mnt/some_mount_point/image_store/somedir/some_image.jpg
                 and
             http://www.mydomain.org/photos/originals/somedir/some_image.jpg
         point to the same file, one locally, one via the web server

     WEB_ORIGINALS_ROOT: this is the root directory of the originals relative to the
         web server. Using the example above, this would be:
             /photos/originals

     URL_BASE: is the part of the URL added to the web server's address to this cgi script
         for example:
             /cgi-bin/webalbum.py
         meaning the full url might be http://www.mydomain.org/cgi-bin/webalbum.py

     PREVIEW_FILE_DIR: this is the local directory where the generated thumbnails and
         view sized images are to be written to be displayed by the web server. This needs
         to be a directory whose contents can be accessed via the web server.
         eg: /var/www/webalbum

     WEB_PREVIEW_FILE_DIR: this is the same directory as PREVIEW_FILE_DIR but relative
         to the web root directory/export            192.168.20.0/24(rw,fsid=0,insecure,no_subtree_check,async)

     THUMBNAIL_DIR: a pre-existing subdirectory of PREVIEW_FILE_DIR where the thumbnails will
         written to (appended to PREVIEW_FILE_DIR). eg: /thumbnails

     VIEW_DIR: a pre-existing subdirectory of PREVIEW_FILE_DIR where the view sized images wiill
         be written to (appended to PREVIEW_FILE_DIR). eg: /view

     ERROR_THUMBNAIL: thumbnail image to be displayed when there is an error generating the
         thumnbnail from the original image. eg: WEB_PREVIEW_FILE_DIR+"/error_thumbnail.png"
         The file should preferrably be in WEB_PREVIEW_FILE_DIR

     ERROR_VIEW: view sized image to be displayed when there is an error generating the view
         sized image from the original. eg: ERROR_VIEW=WEB_PREVIEW_FILE_DIR+"/error_view.png"
         The file should preferrably be in WEB_PREVIEW_FILE_DIR

Also make sure to copy the maps-pin.png into the same directory as the error images.

Python Module Requirements:
    - PIL - Python Imaging Library (http://www.pythonware.com/products/pil/)
    - ffvideo (https://pypi.python.org/pypi/FFVideo)

"""
#import logging
#import logging.handlers
#
#logger = logging.getLogger('WebAlbum')
#logger.setLevel(logging.DEBUG)
#
#handler = logging.handlers.SysLogHandler(address = '/dev/log')
#
#logger.addHandler(handler)
#logger.info("test message")


import cgi
import cgitb
import configparser

import traceback
import os, sys, time, pickle
import shlex, subprocess
from subprocess import STDOUT,PIPE
import getpass
import urllib
from PIL import Image
from ffvideo import VideoStream

from PIL.ExifTags import TAGS, GPSTAGS

fs = cgi.FieldStorage()
keys = fs.keys()
clearcache = True if ('clearcache' in keys) and (fs.getvalue('clearcache') == 'on') else False
searchstr = "" if 'searchstr' not in keys else fs.getvalue('searchstr')
video_search = "" if 'video_search' not in keys else fs.getvalue('video_search')

#------ CONFIGURATION SECTION ----------
# optional config file for the config items below
# The config file should look something like below:
############### BEGIN EXAMPLE CONF FILE ###################
# [webalbum]
# GMAPS_API_KEY = aasdfji8f98239487230497asdf
# ALBUM_ROOT = /my/path/to/my/origianl/images/and/videos 
################ END EXAMPLE CONF FILE ####################
CONFIG_FILE="/etc/webalbum/webalbum.conf"

class WebAlbumConfig(object):
    def __init__(self, cfgfile):
        self._cfgfile = cfgfile.strip()
        if os.path.isfile(self._cfgfile):
            self._cfg = configparser.ConfigParser()
            self._cfg.read(self._cfgfile)
            self._data = self._cfg['webalbum']
        else:
            #logger.warning("config file not found, using defaults ({})".format(self._cfgfile))
            self._cfg = None

    def get_value(self, key, default=None):
        if key is None:
            raise ValueError("config key can't be None")

        if self._cfg is None:
            return default
        return self._data.setdefault(key, default)

    def get_str(self, key, default=""):
        return str(self.get_value(key, default=default))

    def get_int(self, key, default=0):
        return int(self.get_value(key, default=default))

cfg = WebAlbumConfig(CONFIG_FILE)

# this is YOUR google maps API key, you need to obtain one if you don't yet have one and
# add it to the CONF_FILE
GMAPS_API_KEY = cfg.get_str("GMAPS_API_KEY", "")

# local root directory containing the original images (the base directory of the source images)
ALBUM_ROOT = cfg.get_str("ALBUM_ROOT", "/mnt/originalphotos")
#ALBUM_ROOT = "/home/jason/Pictures"

# the web directory of the original images relative to the server root (yes, my url contains "httpserver" - long story)
# eg: http://www.mydomain.org/httpserver/photos-orig/ is the web dir where the original photos are
WEB_ORIGINALS_ROOT = cfg.get_str("WEB_ORIGINALS_ROOT", "/photos")

# base url of this cgi script eg: http://www.mydomain.org/cgi-bin/webalbum is the url to the
URL_BASE = cfg.get_str("URL_BASE", "/cgi/webalbum")

# local directory where thumbnails and view sized images get generated (this directory must be visible on the web server)
PREVIEW_FILE_DIR = cfg.get_str("PREVIEW_FILE_DIR", "/var/www/webalbum")

# same as PREVIEW_FILE_DIR except relative to the web root dir
WEB_PREVIEW_FILE_DIR = cfg.get_str("WEB_PREVIEW_FILE_DIR", "/webalbum")

# directory where thumbnails get generated (relative to both local and web dirs)
THUMBNAIL_DIR = cfg.get_str("THUMBNAIL_DIR", "/thumbnails")

# directory where images for viewing get generated (relative to both local and web dirs)
VIEW_DIR = cfg.get_str("VIEW_DIR", "/view")

# path to error images (thumbnail and view sizes) relative to PREVIEW_FILE_DIR
ERROR_THUMBNAIL=WEB_PREVIEW_FILE_DIR+"/error_thumbnail.png"
ERROR_VIEW=WEB_PREVIEW_FILE_DIR+"/error_view.png"

#print "Content-type: text/html\n\n"
#print "<html><h1>WebAlbum</h1><p>{} {} {}</p></html>".format(GMAPS_API_KEY, ALBUM_ROOT, PREVIEW_FILE_DIR)
#sys.exit(0)

class AlbumItem(object):
    def __init__(self, path): # path is the full path of the dir or file on the webserver
        self._set_path(path)
        self._text = self._get_url()
        self._im = None
        self._exif_data = None
        self._gps = None

    def _get_path(self):
        return self._path
    def _set_path(self, value):
        if not value.startswith(ALBUM_ROOT) :
            raise BaseException("AlbumItem(): path not entered with the album root at the beginning: %s" % value)
        value = value[len(ALBUM_ROOT):] # remove the ALBUM_ROOT
        while value.startswith("/"):
            value = value[1:]
        while value.endswith("/"):
            value = value[:-1]
        self._path = value
    path = property(_get_path)

    def _get_full_path(self):
        return ALBUM_ROOT+"/"+self._path
    fullpath = property(_get_full_path)

    def _get_url(self):
        # item is a dir or a file relative to the base dir, no slash at the start
        return URL_BASE + "" if len(self._path) == 0 else "?path="+escape_path(self._path)
    url = property(_get_url)

    def _get_basename(self):
        return os.path.basename(self._path)
    basename = property(_get_basename)

    def _get_basename_short(self):
        bn = os.path.basename(self._path)
        return bn if len(bn) < 21 else bn[:6]+"..."+bn[-8:]
    basename_short = property(_get_basename_short)

    def _get_parentdir(self):
        return os.path.dirname(self._path)
    parentdir = property(_get_parentdir)

    def _get_isdir(self):
        return os.path.isdir(self.fullpath)
    isdir = property(_get_isdir)

    def _get_isfile(self):
        return os.path.isfile(self.fullpath)
    isfile = property(_get_isfile)

    def _get_text(self):
        return self._text
    def _set_text(self, value):
        self._text = value.strip()
    text = property(_get_text, _set_text)

    def _clean(self, string):
        chars = '/ ~!@#$%^&*()+={}[]|\\:;\'?<>,'
        cleaned = string
        for i in range(len(chars)):
            cleaned = cleaned.replace(chars[i], "%d" % ord(chars[i]))
        return cleaned

    def _get_im(self):
        if self._im is None:
            self._im = Image.open(self.fullpath)
        return self._im
    im = property(_get_im)

    def _get_thumbnail(self):
        return urllib.quote(self._clean(self._path),'')+".jpg"
    thumbnail = property(_get_thumbnail)

    def _get_thumbnail_local(self):
        # returns full local file path
        return PREVIEW_FILE_DIR+THUMBNAIL_DIR+"/"+self._get_thumbnail()
    thumbnail_local = property(_get_thumbnail_local)

    def _get_thumbnail_web(self):
        # returns the web server relative path to the file
        return WEB_PREVIEW_FILE_DIR+THUMBNAIL_DIR+"/"+self._get_thumbnail()
    thumbnail_web = property(_get_thumbnail_web)

    def _translate_exif_orientation(self, orientation):
        if orientation == 3:
            return 180
        elif orientation == 6:
            return 270
        elif orientation == 8:
            return 90
        return 0

    def _fix_orientation(self):
        orientation = int(self.exif_data.setdefault("Orientation", 0))
        if orientation == 0:
            return
        elif orientation == 3:
            self._im = self.im.rotate(180, expand=True)
        elif orientation == 6:
            self._im = self.im.rotate(270, expand=True)
        elif orientation == 8:
            self._im = self.im.rotate(90, expand=True)

    def createThumbnail(self, force=False):
        thumbfile = self.thumbnail_local
        try:
            if (not os.path.exists(thumbfile)) or force:
                size = 250,250
                self.im.thumbnail(size)
                self._fix_orientation()
                self.im.save(thumbfile, "JPEG", quality=95)
            return os.path.exists(thumbfile)
        except:
            return False

    def _get_exif_data(self):
        try:
            if self._exif_data is None:
                self._exif_data = get_exif_data(self.im)
        except:
            self._exif_data = {}
        return self._exif_data
    exif_data = property(_get_exif_data)

    def _get_orientation(self):
        if self._exif_data is None:
            self.LoadExif()
        if "Orientation" in self._exif_data.keys():
            self._orientation = self._translate_exif_orientation(self._exif_data["Orientation"])
        else:
            self._orientation = 0
        return self._orientation
    orientation = property(_get_orientation)

    def _get_orientation_css(self):
        tmpOr = self.orientation
        if tmpOr == 270:
            return 90
        if tmpOr == 90:
            return 270
        return tmpOr
    orientation_css = property(_get_orientation_css)

    def LoadExif(self):
        if not self.exif_file_exists:
            self.createExifFile()
        else:
            self.load_exif_data_from_file()
        return self.exif_data

    def load_exif_data_from_file(self):
        # assume file exists
        try:
            ef = open(self.exif_file_local)
            self._exif_data = pickle.load(ef)
            ef.close()
            self.load_gps_from_file()
            return self._exif_data
        except:
            return None

    def _get_exif_file(self):
        return urllib.quote(self._clean(self._path),'')+".exif"
    exif_file = property(_get_exif_file)

    def _get_exif_file_local(self):
        # returns the image exif data file
        return PREVIEW_FILE_DIR+THUMBNAIL_DIR+"/"+self._get_exif_file()
    exif_file_local = property(_get_exif_file_local)

    def createExifFile(self, force=False):
        exiffile = self.exif_file_local
        try:
            if (not os.path.exists(exiffile)) or force:
                ef = open(exiffile, 'wb')
                pickle.dump(self.exif_data, ef)
                ef.close()
                self.createGpsFile(force=force)
            return os.path.exists(exiffile)
        except:
            return False

    def _get_exif_file_exists(self):
        return os.path.exists(self.exif_file_local)
    exif_file_exists = property(_get_exif_file_exists)

    def load_gps_from_file(self):
        # assume file exists
        try:
            with open(self.gps_file_local) as gf:
                self._gps = pickle.load(gf)
            return self._gps
        except:
            return None

    def _get_gps_file(self):
        return urllib.quote(self._clean(self._path),'')+".gps"
    gps_file = property(_get_gps_file)

    def _get_gps_file_local(self):
        # returns the image exif data file
        return PREVIEW_FILE_DIR+THUMBNAIL_DIR+"/"+self._get_gps_file()
    gps_file_local = property(_get_gps_file_local)

    def createGpsFile(self, force=False):
        gpsfile = self.gps_file_local
        try:
            if (not os.path.exists(gpsfile)) or force:
                self._gps = get_lat_lon(self.exif_data)
                if self._gps[0] is None or self._gps[1] is None:
                    return False
                with open(gpsfile, 'wb') as gf:
                    pickle.dump(self._gps, gf)
            return os.path.exists(gpsfile)
        except:
            return False

    def _get_gps_file_exists(self):
        return os.path.exists(self.gps_file_local)
    gps_file_exists = property(_get_gps_file_exists)

    def _get_gps(self):
        return self._gps
    gps = property(_get_gps)

    def _get_haveGps(self):
        return (self._gps is not None) and \
               (self._gps[0] is not None) and \
               (self._gps[1] is not None)
    haveGps = property(_get_haveGps)

    def createView(self, force=False):
        viewFile = self.view_local
        try:
            if (not os.path.exists(viewFile)) or force:
                size = 900,900
                self.im.thumbnail(size)
                self._fix_orientation()
                self.im.save(viewFile, "JPEG", quality=90)
            return os.path.exists(viewFile)
        except:
            return False

    def _get_view(self):
        return urllib.quote(self._clean(self._path),'')+".jpg"
    view = property(_get_view)

    def _get_view_local(self):
        # returns full local file path
        return PREVIEW_FILE_DIR+VIEW_DIR+"/"+self._get_view()
    view_local = property(_get_view_local)

    def _get_view_web(self):
        # returns the web server relative path to the file
        return WEB_PREVIEW_FILE_DIR+VIEW_DIR+"/"+self._get_view()
    view_web = property(_get_view_web)

    def _get_web_original(self):
        return WEB_ORIGINALS_ROOT+"/"+self._path
    web_original = property(_get_web_original)

    def _get_full_view_url(self):
        return self.url+"&full_view=true"
    full_view_url = property(_get_full_view_url)

######## EXIF and GPS info gathering
def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]

                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value

    return exif_data

def _get_if_exist(data, key):
    if key in data:
        return data[key]

    return None

def _convert_to_degress(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)

def get_lat_lon(exif_data):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    lat = None
    lon = None

    if "GPSInfo" in exif_data:
        gps_info = exif_data["GPSInfo"]

        gps_latitude = _get_if_exist(gps_info, "GPSLatitude")
        gps_latitude_ref = _get_if_exist(gps_info, 'GPSLatitudeRef')
        gps_longitude = _get_if_exist(gps_info, 'GPSLongitude')
        gps_longitude_ref = _get_if_exist(gps_info, 'GPSLongitudeRef')

        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degress(gps_latitude)
            if gps_latitude_ref != "N":
                lat = - lat

            lon = _convert_to_degress(gps_longitude)
            if gps_longitude_ref != "E":
                lon = - lon

    return lat, lon


################
# Example ######
################
"""
if __name__ == "__main__":
    import sys
    # image = Image.open("/mnt/hddData/photos/2014/2014_02_06-Warialda/20140206_140808.jpg")
    image = Image.open(sys.argv[1])
    sys.stdout.write(sys.argv[1]+" ")
    exif_data = get_exif_data(image)
    exif_data = get_exif_data(image)
    print get_lat_lon(exif_data)
"""
####################################

def get_css():
    return """<STYLE type="text/css">
    h1 { color: #0000aa;
         border: 1px solid #000000;
         filter: progid:DXImageTransform.Microsoft.gradient(startColorstr='#ffaaaaaa', endColorstr='#ffdddddd');
         background: -moz-linear-gradient(top, #aaaaaa, #dddddd);
         background: -webkit-gradient(linear, left top, left bottom, from(#aaaaaa), to(#dddddd));
         padding: 1px 2px 2px 5px;
         font-weight: bold;
         margin: 12px 0px 0px 0px;
         font-size: 2em;
    }
    html { height: 100%;  width: 100%; }
    body {
      font-family: "Gill Sans", sans-serif;
      font-size: 12pt;
      margin: 0em;
      background: #dddddd;
      height: 100%;
      width: 97%;
      vertical-align: middle;
      margin-left: auto;
      margin-right: auto;
      padding-top: 0px;
      padding-bottom: 20px;
    }
    a {
        color: #0000aa;
        text-decoration: none;
    }
    table.dirs {
        border-collapse: collapse;
        border: 1px solid #999;
    }
    td.dirs {
        border-collapse: collapse;
        border: 1px solid #999;
    }
    #footer {
            color: black;
            font-size: 70%;
            width: 100%;
            text-align: right;
            border: 1px solid #000000;
            filter: progid:DXImageTransform.Microsoft.gradient(startColorstr='#ffaaaaaa', endColorstr='#ffdddddd');
            background: -moz-linear-gradient(top, #aaaaaa, #dddddd);
            background: -webkit-gradient(linear, left top, left bottom, from(#aaaaaa), to(#dddddd));
            padding: 1px 2px 2px 5px;
            padding-top: 10px;
    }
    .buttonwidth1 {
            width: 120px;
    }

    #map-canvas { 
            height: 600px;
            width: 900px;
            margin: 0; 
            padding: 0;
    }
  </STYLE>
"""

def filter_isdir(path):
    return os.path.isdir(path)

def filter_is_valid_file(path):
    if not os.path.isfile(path):
        return False
    basename = os.path.basename(path)
    for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        if basename.lower().endswith(ext):
            return True
    return False

def filter_is_valid_video(path):
    if not os.path.isfile(path):
        return False
    basename = os.path.basename(path)
    for ext in ['.avi', '.mp4', '.m4v', '.mov']:
        if basename.lower().endswith(ext):
            return True
    return False

def separate_files(fullPaths):
    dirs = filter(filter_isdir, fullPaths)
    dirItems = [AlbumItem(d) for d in dirs]
    sortedDirs = sorted(dirItems, key=lambda item: item.path)

    files = filter(filter_is_valid_file, fullPaths)
    fileItems = [AlbumItem(f) for f in files]
    sortedFiles = sorted(fileItems, key=lambda item: item.path)

    videos = filter(filter_is_valid_video, fullPaths)
    videoItems = [AlbumItem(f) for f in videos]
    sortedVideos = sorted(videoItems, key=lambda item: item.path)

    return sortedDirs, sortedFiles, sortedVideos

def GetFilesAndDirs(subDir):
    if subDir.endswith("/"):
       subDir = subDir[:-1]
    if subDir.startswith("/"):
        subDir = subDir[1:]
    path = ALBUM_ROOT+"/"+subDir
    if not path.endswith("/") and path!="":
        path += "/"
    contents = os.listdir(path)
    #print contents
    fullPaths = [path+d for d in contents]
    return separate_files(fullPaths)


def HTML_Header(page_title):
    out = "Content-type: text/html\n\n"
    #out += "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">\n"
    out += "<!DOCTYPE html>\n"
    out += "<html>\n<head>\n<meta http-equiv=\"X-UA-Compatible\" content=\"IE=7\">\n"
    #out += "  <link href=\"/css/webalbum.css\" rel=\"stylesheet\" type=\"text/css\"/>\n"
    #out += "  <link href=\"/pixmaps/site.ico\" rel=\"shortcut icon\"/>\n"
    out += "  <title>%s</title>\n" % page_title
    out += get_css()
    out += """    <script type="text/javascript"
      src="https://maps.googleapis.com/maps/api/js?key=API_KEY">
    </script>
    <script type="text/javascript">
    var map;
    var bounds = new google.maps.LatLngBounds();
    function initialize() {
        map = new google.maps.Map(document.getElementById('map-canvas'),
            get_map_options());
        addMarkers();
    }

    google.maps.event.addDomListener(window, 'load', initialize);
    </script>
""".replace("API_KEY", GMAPS_API_KEY)
    out += "</head>\n<body>\n"
    #out += "<h1>Web Album</h1>\n"
    out += render_search_form(searchstr)
    out += "</br>\n"
    return out

def HTML_Footer():
    out = "     </td></tr></table></center>\n"
    out += "<br/><table id=\"footer\"><tr><td>Dynamically created by webalbum python based cgi - Jason Milen 2013</td></tr></table>\n"
    out += "</body>\n</html>\n"
    return out

def HTML_Header_Thin():
    return """Content-type: text/html

<!DOCTYPE html>
<html>
    <head>
        <meta http-equiv="X-UA-Compatible" content="IE=7">
        <style type="text/css">
            .rotate90 {
                -webkit-transform: rotate(90deg);
                -moz-transform: rotate(90deg);
                -o-transform: rotate(90deg);
                -ms-transform: rotate(90deg);
                transform: rotate(90deg);
            }
             .rotate180 {
                -webkit-transform: rotate(180deg);
                -moz-transform: rotate(180deg);
                -o-transform: rotate(180deg);
                -ms-transform: rotate(180deg);
                transform: rotate(180deg);
            }
              .rotate270 {
                -webkit-transform: rotate(270deg);
                -moz-transform: rotate(270deg);
                -o-transform: rotate(270deg);
                -ms-transform: rotate(270deg);
                transform: rotate(270deg);
            }
        </style>
        <title>Image Only</title>
    </head>
    <body>
"""

def HTML_Footer_Thin(orientation=0):
    orientation = int(orientation)
    out = """
<script type="text/javascript">
window.onload = function() { doResize(); }
window.onresize = function() { doResize(); }
window.onorientationchange = function() { doResize(); }

function doResize(){
  // alert("onload entered");
  var pic = document.getElementById("fullsize");
  var docElem = document.getElementsByTagName("body")[0];
  var h = pic.offsetHeight;
  var w = pic.offsetWidth;
  var picRatio = (h).toFixed(2)/(w).toFixed(2);

  h = window.innerHeight;
  w = window.innerWidth;
  var winRatio = (h).toFixed(2)/(w).toFixed(2);
  if (picRatio < winRatio){
    // alert("setting width");
    // remove height settings
    pic.style.height = "";
    docElem.style.height = (window.innerHeight-100) + "px";
    pic.style.width = "100%";
  }
  else {
    // alert("setting height");
    // remove width settings
    pic.style.width = "";
    docElem.style.height = (window.innerHeight-100) + "px";
    pic.style.height = "100%";
  }
}
</script>
    </body>
</html>
"""
    return out

def GetRequestMethod():
    return os.environ['REQUEST_METHOD']

def get_path():
    path = urllib.unquote(fs.getvalue("path") if 'path' in keys else "")
    return path

def escape_path(path):
    bits = path.split("/")
    return "/".join([urllib.quote(bit,'') for bit in bits])

def isFullView():
    return "full_view" in keys

def GetDirUrls(item, dirs):
    urls = []
    parent = AlbumItem(ALBUM_ROOT+"/"+item.parentdir)
    urls.append(parent.url)
    for d in dirs:
        urls.append(d.url)
    return urls

def GetLink(url, linkText, newTab=False):
    target = ' target="_blank"' if newTab else ''
    return '<a href="'+url+'"'+target+'>'+linkText+'</a>'

def render_search_form(preload=""):
    out =  '<form method="GET">\n'
    out += '<h1><table width="100%"><tr align="left">\n'
    out += '<td>Web Album</td>\n'
    out += '<td align="right">\n'
    out += '<input id="cb_clearcache" name="clearcache" type="checkbox" onclick="javascript:cb_cache_click();"/>\n'
    out += '<input type="text" name="searchstr" value="%s"/>' % preload
    out += '<input id="btn_search" class="buttonwidth1" type="submit" value="Search"/></td>\n'
    out += '</tr></table></h1>\n'
    out += '</form>\n'
    out += """<script type="text/javascript">
function cb_cache_click() {
    var btn_text;
    if (document.getElementById("cb_clearcache").checked) {
        btn_text = "Clear Cache";
    } else {
        btn_text = "Search";
    }
    document.getElementById("btn_search").value = btn_text;
}
</script>
"""
    return out

def render_parent_prev_next(item):
    tmpitem = AlbumItem(ALBUM_ROOT+'/'+item.parentdir) if item.isfile else item
    parent = AlbumItem(ALBUM_ROOT+'/'+tmpitem.parentdir)
    siblingDirs, siblingFiles, siblingVideos = GetFilesAndDirs(parent.path)
    dirIndex = get_item_index(tmpitem, siblingDirs)
    parent.text = 'Parent Directory'

    out = ''
    out += '<table class="dirs" width="100%"><tr>\n'
    out += '<td class="dirs" width="5%" align="center">'+GetLink(URL_BASE, 'Top')+'</td>\n'
    out += '<td class="dirs" width="15%" align="center">'+GetLink(parent.url, parent.text)+'</td>\n'
    if dirIndex is not None and dirIndex > 0:
        prevDir = siblingDirs[dirIndex -1]
        out += '<td class="dirs" width="40%" align="center">'+GetLink(prevDir.url, 'Prev: '+prevDir.basename)+'</td>\n'
    else :
        out += '<td class="dirs" width="40%" align="center"><font color="#AAAAAA">Prev: </font></td>\n'
    if dirIndex is not None and dirIndex < len(siblingDirs) - 1 :
        nextDir = siblingDirs[dirIndex + 1]
        out += '<td class="dirs" width="40%" align="center">'+GetLink(nextDir.url, 'Next: '+nextDir.basename)+'</td>\n'
    else :
        out += '<td class="dirs" width="40%" align="center"><font color="#AAAAAA">Next: </font></td>\n'
    out += '<td class="dirs" width="5%" align="center">'+GetLink(URL_BASE+'?video_search=1', 'Videos')+'</td>\n'
    out += '</tr></table>\n'
    return out

def GetDirLinksHeading(dirItem):
    out =  '<table width="100%" border="0" cellpadding="3" cellspacking="3">\n'
    #out += "<tr><td><b>Directory Links</b></td><td align=\"right\"><b>"+dirItem.basename+"</b></td></tr>\n"
    out += '<tr><td><b>Directory Links: '+dirItem.basename+'</b></td></tr>\n'
    out += '</table>\n'
    return out

def render_dirs_files_videos(dirs,files,videos,item):
    ppn = render_parent_prev_next(item)
    out = ppn

    if len(dirs) > 0:
        out += GetDirLinksHeading(item)

    for i in range(len(dirs)):
        out += ('' if i == 0 else '<br/>')+GetLink(dirs[i].url, dirs[i].basename)+'\n'

    if len(videos)> 0:
        out += '<br/><b>Video Links</b>\n'
        out += '<br/><center><table>\n'
        columns = 5
        col = 0
        for f in videos:
            if col == 0:
                out += '<tr>\n'
            out += '<td><center>'+get_video_link_with_thumbnail(f)+'</center></td>\n'
            col += 1
            if col == columns:
                col = 0
                out += '</tr>\n'
        out += '</table></center>\n<br/>\n'

    if len(files) > 0:
        gps_items = []
        out += '<br/><b>File Links</b>\n'
        out += '<br/><center><table>\n'
        columns = 5
        col = 0
        for f in files:
            if col == 0:
                out += '<tr>\n'
            out += '<td><center>'+get_file_link_with_thumbnail(f, newTab=True)+'</center></td>\n'
            col += 1
            if col == columns:
                col = 0
                out += '</tr>\n'
            if f.haveGps:
                gps_items.append(f)
        out += '</table></center>\n<br/>\n'
        if len(gps_items) > 0:
            out += '<br/><center><table><tr><td>\n'
            out += addMap(gps_items)
            out += '</td></tr></table></center>\n'

    if (len(dirs) + len(videos) + len(files) > 15) or \
       (len(dirs) > 20):
        out += '<br/><br/>\n' + ppn + '<br/><br/>\n'

    return out

def render_dir_page(item):
    dirs, files, videos = GetFilesAndDirs(item.path)

    out = render_dirs_files_videos(dirs,files,videos,item=item)
    return out

def get_file_link_with_thumbnail(item, newTab=False):
    exif_data = item.LoadExif()
    thumb_ok = item.createThumbnail()

    out = ''
    imgPath = item.thumbnail_web if thumb_ok else ERROR_THUMBNAIL
    thumb_error = '' if thumb_ok else 'ERROR: '
    map_link = '<img src="/webalbum/maps-pin.png">' if item.haveGps else ''
    out += '<br/>'+GetLink(item.url, '<img style="max-width:95%;border:3px solid black;" src="'+\
            imgPath+'"><br/>'+map_link+thumb_error+item.basename_short+'</img>\n', newTab=newTab)
    #out += "<p>%s</p>\n" % str(",".join(exif_data.keys()))
    #out += "<p>%s</p>\n" % str(gps)
    return out

def get_file_link_with_view(item, newTab=False):
    view_ok = item.createView()
    exif_data = item.LoadExif()

    view_error = '' if view_ok else 'ERROR: '
    out = ''
    imgPath = item.view_web if view_ok else ERROR_VIEW
    out += '<br/>'+GetLink(item.full_view_url, '<img style="max-width:95%;border:3px solid black;" src="'+\
            imgPath+'"><br/>'+('' if view_ok else 'ERROR: ')+item.basename+'</img>\n', newTab=newTab)
    return out

def get_video_link_with_thumbnail(item):
    outfile = item.thumbnail_local
    try:
        if not os.path.exists(outfile):
            # make video thumbnail
            try:
                pil_image = VideoStream(item.fullpath).get_frame_at_sec(5).image()
            except:
                try:
                    pil_image = VideoStream(item.fullpath).get_frame_at_sec(0.5).image()
                except:
                    pil_image = VideoStream(item.fullpath).get_frame_at_sec(0).image()
            size = 250,250
            pil_image.thumbnail(size)
            pil_image.save(outfile)
        fileOk=True
    except:
        fileOk=False
    out = ''
    imgPath = item.thumbnail_web if fileOk else ERROR_THUMBNAIL
    out += '<br/>'+GetLink(item.web_original, '<img style="max-width:95%;border:3px solid black;" src="'+\
            imgPath+'"><br/>'+('' if fileOk else 'ERROR: ')+item.basename_short+'</img>\n', newTab=True)
    return out


def get_item_index(item, items):
    """ intended to return the index of the current item in the list of files in the directory """
    itemPaths = [i.path for i in items]
    if item.path=='' or item.path not in itemPaths:
        return None
    return itemPaths.index(item.path)

def render_file_page(item):
    parent = AlbumItem(ALBUM_ROOT+'/'+item.parentdir)
    out = render_parent_prev_next(item)
    out += GetDirLinksHeading(parent)
    out += '<center>\n'
    parent.text = 'Back to directory gallery'
    dirs, files, videos = GetFilesAndDirs(parent.path)
    fileIndex = get_item_index(item, files) # get the index of the file in the list of files in the directory
    out += '<table width="100%">\n<tr><td width="20%" align="top"><center>'
    if fileIndex > 0:
        out += get_file_link_with_thumbnail(files[fileIndex-1])
    out += '</center></td>\n<td><center>'
    out += '<br/>'+GetLink(parent.url, parent.text)+'<br/>\n'
    out += get_file_link_with_view(item, newTab=True)
    out += '<br/>Click image to see full size original\n'
    out += '</center></td>\n<td width="20%" align="top"><center>'
    if fileIndex < len(files) - 1:
        out += get_file_link_with_thumbnail(files[fileIndex+1])
    out += '</center></td>\n</tr>\n'
    out += '</table>\n'
    if item.haveGps:
        out += addMap(item)
    out+='</center>\n'

    return out

def render_full_image(item, nextImageLink=None):
    img = '<img id="fullsize" src="%s" style="width: 100%%; height: 100%%;" class="rotate%d"/>' \
          % (item.web_original, item.orientation_css)
    if nextImageLink is None:
        return img+'\n' 
    else :
        return '<a href="%s">\n%s\n</a>\n' % (nextImageLink, img)

def test_fs(item):
    out = """Content-type: text/html

<!DOCTYPE html>
<html>
    <head>
        <meta http-equiv="X-UA-Compatible" content="IE=7">
        <title>Image Only</title>
    </head>
    <body>

<script type="text/javascript">
window.onload = function() { doResize(); }
window.onresize = function() { doResize(); }

function doResize(){
  // alert("onload entered");
  var pic = document.getElementById("fullsize");
  var docElem = document.getElementsByTagName("body")[0];
  var h = pic.offsetHeight;
  var w = pic.offsetWidth;
  var picRatio = (h).toFixed(2)/(w).toFixed(2);

  h = window.innerHeight;
  w = window.innerWidth;
  var winRatio = (h).toFixed(2)/(w).toFixed(2);

  if (picRatio < winRatio){
    // alert("setting width");
    // remove height settings
    pic.style.height = "";
    docElem.style.height = "";
    pic.style.width = "100%";
  }
  else {
    // alert("setting height");
    // remove width settings
    pic.style.width = "";
    docElem.style.height = "100%";
    pic.style.height = "100%";
  }
}
</script>
    </body>
</html>
"""
    return out

def render_full_view_file_page(item):
    """ This writes a very basic page with just the full size original as the body, 
    and the image links to the next full size original """
    #return test_fs(item) 

    parent = AlbumItem(ALBUM_ROOT+'/'+item.parentdir)
    dirs, files, videos = GetFilesAndDirs(parent.path)
    fileIndex = get_item_index(item, files) # get the index of the file in the list of files in the directory
    out = HTML_Header_Thin()
    if fileIndex < len(files) - 1:
        nextImageLink = files[fileIndex+1].full_view_url
    else:
        nextImageLink = None
    out += render_full_image(item, nextImageLink=nextImageLink)
    return out+HTML_Footer_Thin(item.orientation)


def unique_gps_items(items):
    """ The purpose of this function is to take a list of items with
    gps positions and filter out the items that have duplicate gps positions
    so that the list only has unique gps positions """
    ugi = []
    for item in items:
        unique = True
        for i in ugi:
            if i.gps == item.gps:
                unique = False
                break
        if unique:
            ugi.append(item)
    return ugi

def addMap(items):
    if type(items) is not list:
        items = [items]

    items = unique_gps_items(items)

    minLat = +1000.0
    maxLat = -1000.0
    minLon = +1000.0
    maxLon = -1000.0
    for i in range(len(items)):
        minLat = min(minLat, float(items[i].gps[0]))
        maxLat = max(maxLat, float(items[i].gps[0]))
        minLon = min(minLon, float(items[i].gps[1]))
        maxLon = max(maxLon, float(items[i].gps[1]))
    if len(items) < 2 :
        centre_gps = items[0].gps
    else:
        centre_gps = ('%0.8f' % ((minLat + maxLat)/2.0),
                      '%0.8f' % ((minLon + maxLon)/2.0))

    out  = '<div id="map-canvas"></div>\n'
    out += '<script type="text/javascript">\n'
    out += 'function get_map_options() {\n'
    out += '    var mapOptions = {\n'
    out += '        center: { lat: %s, lng: %s},\n' % (centre_gps[0], centre_gps[1])
    out += '        zoom: 16\n'
    out += '    };\n'
    out += '    return mapOptions;\n'
    out += '}\n'
    out += 'function addMarkers() {\n'
    out += '    var latlng;'
    for i in range(len(items)):
        out += '    latlng = new google.maps.LatLng(%s,%s),\n' % (items[i].gps[0], items[i].gps[1])
        out += '    marker = new google.maps.Marker({\n'
        out += '        position: latlng,\n'
        out += '        map: map\n'
        out += '    });\n'
        out += '    google.maps.event.addListener(marker, "click", function () {\n'
        out += '            window.open("%s", "_blank");\n' % items[i].url
        out += '    });\n'
        out += '    bounds.extend (latlng);\n'

    if len(items) > 1:
        out += '    map.fitBounds(bounds);\n'

    out += '}\n'
    out += '</script>\n'
    return out

def render_error_page(path):
    return ''

def render_search(searchstr, rootItem):
    cmd = 'find %s -iname "*%s*"' % (ALBUM_ROOT, searchstr)
    p = subprocess.Popen(shlex.split(cmd), stdout=PIPE)
    stdout,stderr = p.communicate()
    found_objects = sorted([o.strip() for o in stdout.split("\n") if len(o.strip()) > 0])
    dirs, files, videos = separate_files(found_objects)
    return render_dirs_files_videos(dirs, files, videos, item=rootItem)

def render_video_search(rootItem):
    cmd = 'find %s -regextype sed -iregex ".*/.*\(mp4\|avi\)"' % ALBUM_ROOT
    p = subprocess.Popen(shlex.split(cmd), stdout=PIPE)
    stdout,stderr = p.communicate()
    found_objects = sorted([o.strip() for o in stdout.split('\n') if len(o.strip()) > 0])
    dirs, files, videos = separate_files(found_objects)
    return render_dirs_files_videos(dirs, files, videos, item=rootItem)

def render_clear_cache(searchstr, item):
    searchstr = searchstr.strip()
    thumbdir = PREVIEW_FILE_DIR+THUMBNAIL_DIR+'/'
    viewdir  = PREVIEW_FILE_DIR+VIEW_DIR+'/'
    cmdthumbs = 'find %s -iname "*%s*" -exec rm {} \;' % (thumbdir, searchstr)
    cmdviews  = 'find %s -iname "*%s*" -exec rm {} \;' % (viewdir, searchstr)
    out = ''
    #out += cmdthumbs+"<br/>"+cmdviews+"<br/>"
    p = subprocess.Popen(shlex.split(cmdthumbs), stdout=PIPE)
    stdout, stderr = p.communicate()
    #out += str(stdout)+"<br/>"+str(stderr)+"<br/>"
    p = subprocess.Popen(shlex.split(cmdviews), stdout=PIPE)
    stdout, stderr = p.communicate()
    #out +=  str(stdout)+"<br/>"+str(stderr)+"<br/>"
    out += '<br/>Files cleared<br/>\n\n' + render_dir_page(item)
    return out

def render_page():
    try:
        reqMethod = GetRequestMethod()
        #if reqMethod=="POST":
        #    pass
        path = get_path()

        item = AlbumItem(ALBUM_ROOT+'/'+path)
        full_view = isFullView()
        if full_view:
            page = render_full_view_file_page(item)
        elif len(searchstr) > 0:
            if clearcache:
                page = render_clear_cache(searchstr, item)
            else:
                page = render_search(searchstr,item)
        elif video_search == '1':
            page = render_video_search(item)
        elif item.isdir:
            page = render_dir_page(item)
        elif item.isfile:
            page = render_file_page(item)
        else:
            page = render_error_page(item)

        if not full_view:
            sys.stdout.write(HTML_Header('Photo Gallery'))

        sys.stdout.write(page)

        if not full_view:
            sys.stdout.write(HTML_Footer())
    except:
        sys.stdout.write('Content type: text/html\n\n')
        sys.stdout.write(traceback.format_exc())

if __name__ == '__main__':
    cgitb.enable() # enable error info in the webpage
    render_page()

