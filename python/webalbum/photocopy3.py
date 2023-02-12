#!/usr/bin/env python3

# photocopy3.py - Jason Milen, June 2012 (This is the python3 version of photocopy.py)
#
# The purpose of this python script is to copy photos and videos directly off Compact Flash
# or SD cards from cameras, USB drives or direct connection to a phone (and so on) and copy
# all the photos, videos and other files into a series of directories which are in the format:
#    [DESTINATION_ROOT]/YYYY/YYYY_MM_DD/
#
# There is an extra thing which I need and that is if I rename a destination folder like this:
#    [DESTINATION_ROOT]/YYYY/YYYY_MM_DD-some-description/
# and run the copy operation on new photos then a file which would normally go into that dated folder
# will still go into the folder with the modified name rather than a new folder with the same date.


import hashlib
import logging
from logging import handlers
import optparse
import os
import sys
from pathlib import Path
from random import randint
import shutil
import time
import traceback

from PIL import Image
from PIL.ExifTags import TAGS
from PIL import UnidentifiedImageError

# used for hashing files
BLOCK_SIZE = 65536  # The size of each read from the file

# setup logging to stdout and syslog
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)
formatter_stdout = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
formatter_syslog = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler_stdout = logging.StreamHandler(sys.stdout)
handler_syslog = handlers.SysLogHandler(address='/dev/log')
handlers_and_formatters = [
    (handler_stdout, formatter_stdout),
    (handler_syslog, formatter_syslog),
]
for handler, formatter in handlers_and_formatters:
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def format_date(day, month, year):
    return str(year) + '_' + str(month) + '_' + str(day)


def get_hash(_file):
    """
    Return the sha256sum of the specified file in hex-string format.
    """
    file_hash = hashlib.sha256()  # Create the hash object, can use something other than `.sha256()` if you wish
    with open(str(_file), 'rb') as f:  # Open the file to read it's bytes
        fb = f.read(BLOCK_SIZE)  # Read from the file. Take in the amount declared above
        while len(fb) > 0:  # While there is still data being read from the file
            file_hash.update(fb)  # Update the hash
            fb = f.read(BLOCK_SIZE)  # Read the next block from the file
    return file_hash.hexdigest()  # returns the familiar hex string format


def rename_destfile(path):
    if not isinstance(path, Path):
        path = Path(path)
    suffix = path.suffix
    return "{}-{:03d}{}".format(str(path)[:-len(suffix)], randint(0, 1000), suffix)


# get embedded image data
def get_exif_image(filepath):
    ret = {}
    try:
        i = Image.open(filepath)
    except UnidentifiedImageError as exc:
        logger.error(f"Error reading file as image (maybe it isn't an image?): {filepath} {str(exc)}")
        return None

    info = i._getexif()
    if not hasattr(info, 'items'):
        logger.error(f"No EXIF data found in image: {filepath}")
        return None
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        ret[decoded] = value
    return ret


def get_date_from_filename(filepath):
    """If the filename is of the format YYYYMMDD_hhmmss
    """
    logger.debug(f"DEBUG: {filepath}")
    fname = os.path.basename(filepath)
    logger.debug(f"DEBUG: {fname}")
    date = fname.split("_")[0]
    if len(date) != 8:
        logger.debug(f"DEBUG: {date}")
        logger.debug("DEBUG: date len != 8")
        return None
    try:
        int(date)  # will raise an exception if not all digits
        if date[0:2] != '20':
            return None
        date_str = "%s %s %s" % (date[0:4], date[4:6], date[6:8])
        retval = time.strptime(date_str, "%Y %m %d")
        return retval
    except Exception as exc:
        traceback.print_exc()
        logger.debug(f"debug: exc {str(exc)}")
        return None


def get_file_date(filepath):
    creationTime = time.localtime(os.path.getctime(filepath))
    return creationTime


def make_time_from_date(day, month, year):
    return time.localtime(time.mktime((int(year), int(month), int(day), 12, 0, 0, 0, 0, 0)))


# Get all the subdirectories of the rootdir
def get_dirs(rootdir):
    paths = []
    for (path, dirs, files) in os.walk(rootdir):
        paths.append(path)
    return paths


# get all the files within and in the subdirs of rootdir. Files are returned with the path
def get_files(rootdir):
    fullFileList = []
    for (path, dirs, files) in os.walk(rootdir):
        for f in files:
            # this double os.sep replace is needed because linux and windows don't behave
            # the same with the os.sep at the end of the path
            filePath = (path + os.sep + f).replace(os.sep + os.sep, os.sep)
            if os.path.isfile(filePath):  # just a double check
                fullFileList.append(filePath)
    return fullFileList


def path_with_separator(path):
    new_path = path.strip()
    if new_path[-1] != os.sep:
        new_path = new_path + os.sep
    return new_path


def path_without_separator(path):
    new_path = path.strip()
    if new_path[-1] == os.sep:
        new_path = new_path[:-1]
    return new_path


# File class is used to self determine the file date but the date will come from the EXIF
# data in a JPG if the data can be extracted.
class File:
    def __init__(self, image_file_path):
        self.image_file_path = image_file_path
        self.exif = get_exif_image(image_file_path)
        if self.exif is not None:
            try:
                self.dateExif = self.exif['DateTimeOriginal']
            except Exception as exc:
                self.dateExif = None
                logger.error(f"ERROR: exception {str(exc)}")
        self.get_date()
        self.date_str = self.get_date_str()
        self.year = self.date_str[:4]

    def get_date(self):
        if self.exif is None or self.dateExif is None:
            # try to get the date from the file name
            self.date = get_date_from_filename(self.image_file_path)
            if self.date is None:
                # if that fails, get the date from the file date
                self.date = get_file_date(self.image_file_path)
        else:
            tmp_date = self.dateExif[:10].split(":")
            # if the date is '-' separated rather than ':' separated
            # then handle that case
            if len(tmp_date) < 3:
                tmp_date = tmp_date[0].split("-")
            logger.info(tmp_date)
            self.date = make_time_from_date(tmp_date[2], tmp_date[1], tmp_date[0])

    def get_date_str(self):
        return format_date(self.date.tm_mday, self.date.tm_mon, self.date.tm_year)


class CopySet:
    def __init__(self, src_dir, dst_dir, overwrite=False, preserve_spaces=True, delete_orig=False):
        self.src_dir = path_with_separator(src_dir.strip())
        self.dst_dir = path_with_separator(dst_dir.strip())
        self.get_dst_sub_dirs()
        self.get_src_files()
        self.get_src_files_jpg()
        self.get_src_files_other
        self.overwrite = overwrite
        self.preserve_spaces = preserve_spaces
        self.delete_orig = delete_orig

    def get_dst_sub_dirs(self):
        self.dirs = get_dirs(self.dst_dir)
        return self.dirs

    def get_src_files(self):
        self.files = get_files(self.src_dir)
        return self.files

    def get_src_files_jpg(self):
        self.src_files_jpg = [x for x in self.files if x[-4:].lower() == ".jpg"]
        return self.src_files_jpg

    def get_src_files_other(self):
        self.src_files_other = [x for x in self.files if x[-4:].lower() != ".jpg"]
        return self.src_files_other

    def get_dst_dir(self, date):
        dst_dir = f"{self.dst_dir}{str(date.tm_year)}{os.sep}"
        dst_dir += "%04d_%02d_%02d" % (date.tm_year, date.tm_mon, date.tm_mday)
        already = [x for x in self.dirs if x.find(dst_dir) >= 0]
        if already != []:
            dst_dir = already[0]
        logger.info(f"dst_dir {dst_dir}")
        return dst_dir

    def copy_files(self):
        logger.info(f"number of files {len(self.files)}")
        for f in self.files:
            logger.info(f)
            fileToCopy = File(f)
            dstDir = self.get_dst_dir(fileToCopy.date)
            if self.preserve_spaces:
                destFile = dstDir + os.sep + os.path.basename(f)
            else:
                destFile = dstDir + os.sep + os.path.basename(f).replace(" ", "_")
            if not (os.path.isdir(dstDir)):
                os.makedirs(dstDir)
                logger.info(f"Folder for renaming: {dstDir}")
            if not os.path.isfile(destFile):
                logger.info(f"Copy {os.path.basename(f)} -> {destFile}")
                shutil.copy(f, destFile)
            else:
                if self.overwrite:
                    logger.warning(f"Copying over destination file which already exists: {destFile}")
                    shutil.copy(f, destFile)
                else:
                    src_hash = get_hash(f)
                    dst_hash = get_hash(destFile)
                    if src_hash == dst_hash:
                        logger.info(f"Destination file already exists and is the same: {destFile}")
                    else:
                        logger.info(f"Renaming desination file to not overwriting file with the same name: {destFile}")
                        destFile = rename_destfile(destFile)
                        shutil.copy(f, destFile)
            if self.delete_orig:
                if (os.path.isfile(destFile) and
                        os.path.getsize(destFile) == os.path.getsize(f)):
                    try:
                        os.remove(f)
                    except Exception as exc:
                        logger.error(f"failed to delete file: {f} {str(exc)}")


def main():
    parser = optparse.OptionParser()
    parser.add_option("-s", "--sourcedir", dest="srcdir",
                      help="source directory of files to be copied", metavar="SRCDIR", default="NULL")
    parser.add_option("-d", "--destdir", dest="dstdir",
                      help="destination directory where the files are to be copied", metavar="DSTDIR", default="NULL")
    parser.add_option("-o", action="store_true", dest="overwrite", default=False,
                      help="if the destination file already exists this option will cause the file to be overwritten")
    parser.add_option("-p", action="store_true", dest="preserve_spaces", default=False,
                      help="this option will stop the file names from having spaces replaced with \"_\"")
    parser.add_option("-D", action="store_true", dest="delete_orig", default=False,
                      help="attempt to delete the original file once it has been copied")

    (options, args) = parser.parse_args()

    if not os.path.isdir(options.srcdir):
        logger.error(f"Error: the source directory does not exist:\n\t{options.srcdir}")
        return 1
    if not os.path.isdir(options.dstdir):
        logger.error(f"Error: the destination directory does not exist:\n\t{options.dstdir}")
        return 1

    copy_set = CopySet(options.srcdir, options.dstdir, options.overwrite, options.preserve_spaces, options.delete_orig)
    copy_set.copy_files()
    return 0


if __name__ == '__main__':
    sys.exit(main())
