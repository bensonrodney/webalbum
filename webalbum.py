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
         to the web root directory

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

"""

import cgi
import cgitb


import os, sys, time
import shlex, subprocess
import getpass
import urllib
import Image


#------ CONFIGURATION SECTION ----------
# optional config file for the config items below
CONFIG_FILE="/usr/lib/cgi-bin/webalbum.conf"
def get_conf_item(param):
    def get_attr(attr):
        attr = attr.strip()+"="
        l = [l for l in lines if l.startswith(attr)]
        if len(l) < 1:
            return None
        return l[0][len(attr):].strip()

    f = open(CONFIG_FILE, 'r')
    lines = [l for l in f]
    f.close()
    value = get_attr(param)
    return value

# local root directory containing the original images (the base directory of the source images)
ALBUM_ROOT="/mnt/hddData/photos"

# the web directory of the original images relative to the server root (yes, my url contains "httpserver" - long story)
# eg: http://www.mydomain.org/httpserver/photos-orig/ is the web dir where the original photos are
WEB_ORIGINALS_ROOT="/httpserver/photos-orig"

# base url of this cgi script eg: http://www.mydomain.org/cgi-bin/webalbum is the url to the 
URL_BASE="/cgi-bin/webalbum"

# local directory where thumbnails and view sized images get generated (this directory must be visible on the web server)
PREVIEW_FILE_DIR="/var/www/webalbum"

# same as PREVIEW_FILE_DIR except relative to the web root dir 
WEB_PREVIEW_FILE_DIR="/webalbum" 

# directory where thumbnails get generated (relative to both local and web dirs)
THUMBNAIL_DIR="/thumbnails"

# directory where images for viewing get generated (relative to both local and web dirs)
VIEW_DIR="/view" 

# path to error images (thumbnail and view sizes) relative to PREVIEW_FILE_DIR
ERROR_THUMBNAIL=WEB_PREVIEW_FILE_DIR+"/error_thumbnail.png"
ERROR_VIEW=WEB_PREVIEW_FILE_DIR+"/error_view.png"

class AlbumItem(object):
    def __init__(self, path): # path is the full path of the dir or file on the webserver
        self._set_path(path)
        self._text = self._get_url()
        
    def _get_path(self):
        return self._path
    def _set_path(self, value):
        if not value.startswith(ALBUM_ROOT) :
            raise BaseException("AlbumItem(): path not entered with the album root at the beginning")
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
    body { 
      font-family: "Gill Sans", sans-serif;
      font-size: 12pt;
      margin: 0em; 
      background: #dddddd;
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

    dirs = filter(filter_isdir, fullPaths)
    dirItems = [AlbumItem(d) for d in dirs]
    sortedDirs = sorted(dirItems, key=lambda item: item.path)

    files = filter(filter_is_valid_file, fullPaths)
    fileItems = [AlbumItem(f) for f in files]
    sortedFiles = sorted(fileItems, key=lambda item: item.path)

    return sortedDirs, sortedFiles

def HTML_Header(page_title):
    out = "Content-type: text/html\n\n"
    out += "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">\n"
    out += "<html>\n<head>\n<meta http-equiv=\"X-UA-Compatible\" content=\"IE=7\">\n"
    out += "  <link href=\"/css/webalbum.css\" rel=\"stylesheet\" type=\"text/css\"/>\n"
    #out += "  <link href=\"/pixmaps/site.ico\" rel=\"shortcut icon\"/>\n"
    out += "  <title>%s</title>\n" % page_title
    out += get_css()
    out += "</head>\n<body>\n"
    out += "<h1>Web Album</h1>\n"
    return out

def HTML_Footer():
    out = "     </td></tr></table></center>\n"
    out += "<br/><table id=\"footer\"><tr><td>Dynamically created by webalbum python based cgi - Jason Milen 2013</td></tr></table>\n"
    out += "</body>\n</html>\n"
    return out

def GetRequestMethod():
    return os.environ['REQUEST_METHOD']

def doPostRequest():
    fs = cgi.FieldStorage()
    keys = fs.keys()
    path = urllib.unquote(fs.getvalue("path") if 'path' in keys else "")
    return path

def escape_path(path):
    bits = path.split("/")
    return "/".join([urllib.quote(bit,'') for bit in bits])


def GetDirUrls(item, dirs):
    urls = []
    parent = AlbumItem(ALBUM_ROOT+"/"+item.parentdir)
    urls.append(parent.url)
    for d in dirs:
        urls.append(d.url)
    return urls

def GetLink(url, linkText, newTab=False):
    target = " target=\"_blank\"" if newTab else ""
    return "<a href=\""+url+"\""+target+">"+linkText+"</a>"

def render_parent_prev_next(item):
    tmpitem = AlbumItem(ALBUM_ROOT+"/"+item.parentdir) if item.isfile else item
    parent = AlbumItem(ALBUM_ROOT+"/"+tmpitem.parentdir)
    siblingDirs, siblingFiles = GetFilesAndDirs(parent.path)
    dirIndex = get_item_index(tmpitem, siblingDirs)
    parent.text = "Parent Directory"

    out = ""
    out += "<table class=\"dirs\" width=\"100%\"><tr>\n"
    out += "<td class=\"dirs\" width=\"5%\" align=\"center\">"+GetLink(URL_BASE, "Top")+"</td>\n"
    out += "<td class=\"dirs\" width=\"15%\" align=\"center\">"+GetLink(parent.url, parent.text)+"</td>\n"
    if dirIndex is not None and dirIndex > 0:
        prevDir = siblingDirs[dirIndex -1]
        out += "<td class=\"dirs\" width=\"40%\" align=\"center\">"+GetLink(prevDir.url, "Prev: "+prevDir.basename)+"</td>\n"
    else :
        out += "<td class=\"dirs\" width=\"40%\" align=\"center\"><font color=\"#AAAAAA\">Prev: </font></td>\n"
    if dirIndex is not None and dirIndex < len(siblingDirs) - 1 :
        nextDir = siblingDirs[dirIndex + 1]
        out += "<td class=\"dirs\" width=\"40%\" align=\"center\">"+GetLink(nextDir.url, "Next: "+nextDir.basename)+"</td>\n"
    else :
        out += "<td class=\"dirs\" width=\"40%\" align=\"center\"><font color=\"#AAAAAA\">Next: </font></td>\n"
    out += "</tr></table>\n"
    return out

def GetDirLinksHeading(dirItem):
    out = "<table width=\"100%\" border=\"0\" cellpadding=\"3\" cellspacking=\"3\">\n"
    out += "<tr><td><b>Directory Links</b></td><td align=\"right\"><b>"+dirItem.basename+"</b></td></tr>\n"
    out += "</table>\n"
    return out

def render_dir_page(item):
    dirs, files = GetFilesAndDirs(item.path)
    out = GetDirLinksHeading(item)
    dirLinks = render_parent_prev_next(item)
    out += dirLinks

    for d in dirs:
        out += "<br/>"+GetLink(d.url, d.basename)+"\n"
    if len(files) > 0:
        out += "<br/><b>File Links</b>\n"
        out += "<br/><center><table>\n"
        columns = 5
        col = 0
        for f in files:
            if col == 0:
                out += "<tr>\n"
            out += "<td><center>"+get_file_link_with_thumbnail(f, newTab=True)+"</center></td>\n"
            col += 1
            if col == columns:
                col = 0
                out += "</tr>\n"
        out += "</table></center>\n<br/>\n"
        out += "<br/><br/>\n" + dirLinks + "<br/><br/>\n"

    return out

def get_file_link_with_thumbnail(item, newTab=False):
    outfile = item.thumbnail_local
    try:
        if not os.path.exists(outfile):
            size = 250,250
            im = Image.open(item.fullpath)
            im.thumbnail(size)
            im.save(outfile, "JPEG")
        fileOk=True
    except:
        fileOk=False
    out = ""
    imgPath = item.thumbnail_web if fileOk else ERROR_THUMBNAIL
    out += "<br/>"+GetLink(item.url, "<img style=\"max-width:95%;border:3px solid black;\" src=\""+\
            imgPath+"\"><br/>"+("" if fileOk else "ERROR: ")+item.basename+"</img>"+"\n", newTab=newTab)
    return out

def get_file_link_with_view(item, newTab=False):
    outfile = item.view_local
    try:
        if not os.path.exists(outfile):
            size = 900,900
            im = Image.open(item.fullpath)
            im.thumbnail(size)
            im.save(outfile, "JPEG")
        fileOk=True
    except:
        fileOk=False
    out = ""
    imgPath = item.view_web if fileOk else ERROR_VIEW
    out += "<br/>"+GetLink(item.web_original, "<img style=\"max-width:95%;border:3px solid black;\" src=\""+\
            imgPath+"\"><br/>"+("" if fileOk else "ERROR: ")+item.basename+"</img>"+"\n", newTab=newTab)
    return out
    
def get_item_index(item, items):
    """ intended to return the index of the current item in the list of files in the directory """
    itemPaths = [i.path for i in items]
    if item.path=="" or item.path not in itemPaths:
        return None
    return itemPaths.index(item.path)

def render_file_page(item):
    parent = AlbumItem(ALBUM_ROOT+"/"+item.parentdir)
    out = GetDirLinksHeading(parent)
    dirLinks = render_parent_prev_next(item)
    out += dirLinks
    out += "<center>\n"
    parent.text = "Back to directory gallery"
    dirs, files = GetFilesAndDirs(parent.path)
    fileIndex = get_item_index(item, files) # get the index of the file in the list of files in the directory
    out += "<table width=\"100%\">\n<tr><td width=\"20%\" align=\"top\"><center>"
    if fileIndex > 0:
        out += get_file_link_with_thumbnail(files[fileIndex-1])
    out += "</center></td>\n<td><center>"
    out += "<br/>"+GetLink(parent.url, parent.text)+"<br/>\n"
    out += get_file_link_with_view(item, newTab=True)
    out += "<br/>Click image to see full size original\n"
    out += "</center></td>\n<td width=\"20%\" align=\"top\"><center>"
    if fileIndex < len(files) - 1:
        out += get_file_link_with_thumbnail(files[fileIndex+1])
    out += "</center></td>\n</tr>\n</table>\n"
    out+="</center>\n"
    return out

def render_error_page(path):
    return ""

def render_page():
    reqMethod = GetRequestMethod()
    sys.stdout.write(HTML_Header("Photo Gallery"))
    #if reqMethod=="POST":
    #    pass
    path = doPostRequest()
    item = AlbumItem(ALBUM_ROOT+"/"+path)
    if item.isdir:
        page = render_dir_page(item)
    elif item.isfile:
        page = render_file_page(item)
    else:
        page = render_error_page(item)
    sys.stdout.write(page)
    
    sys.stdout.write(HTML_Footer())


if __name__ == '__main__':
    cgitb.enable() # enable error info in the webpage
    render_page()
    
