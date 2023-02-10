#!/usr/bin/env python3

# photocopy.py - Jason Milen, June 2012
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
import optparse
import os
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


def FormatDate(day, month, year):
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
    return "{}-{:03d}{}".format(str(path)[:-len(suffix)], randint(0,1000), suffix)


# get embedded image data
def get_exif_image(filepath):
    ret = {}
    try:
        i = Image.open(filepath)
    except UnidentifiedImageError as exc:
        print(f"Error reading file as image (maybe it isn't an image?): {filepath}")
        return None

    info = i._getexif()
    if not hasattr(info, 'items'):
        print(f"No EXIF data found in image: {filepath}")
        return None
    for tag, value in info.items():
        decoded = TAGS.get(tag, tag)
        ret[decoded] = value
    return ret


def get_date_from_filename(filepath):
    """If the filename is of the format YYYYMMDD_hhmmss
    """
    print(f"debug: {filepath}")
    fname = os.path.basename(filepath)
    print(f"debug: {fname}")
    date = fname.split("_")[0]
    if len(date) != 8:
        print(f"debug: {date}")
        print("debug: date len != 8")
        return None
    try:
        int(date)  # will raise an exception if not all digits
        if date[0:2] != '20':
            return None
        dateStr = "%s %s %s" % (date[0:4], date[4:6], date[6:8])
        retval = time.strptime(dateStr, "%Y %m %d")
        return retval
    except:
        traceback.print_exc()
        return None


def get_file_date(filepath):
    creationTime = time.localtime(os.path.getctime(filepath))
    return creationTime


def MakeTimeFromDate(day, month, year):
    return time.localtime(time.mktime((int(year), int(month), int(day), 12, 0, 0, 0, 0, 0)))


# Get all the subdirectories of the rootdir
def GetDirs(rootdir):
    paths = []
    for (path, dirs, files) in os.walk(rootdir):
        paths.append(path)
    return paths


# get all the files within and in the subdirs of rootdir. Files are returned with the path
def GetFiles(rootdir):
    fullFileList = []
    for (path, dirs, files) in os.walk(rootdir):
        for f in files:
            # this double os.sep replace is needed because linux and windows don't behave the same
            # with the os.sep at the end of the path
            filePath = (path + os.sep + f).replace(os.sep + os.sep, os.sep)
            if os.path.isfile(filePath):  # just a double check
                fullFileList.append(filePath)
    return fullFileList


def PathWithSeparator(path):
    newPath = path.strip()
    if newPath[-1] != os.sep:
        newPath = newPath + os.sep
    return newPath


def PathWitoutSeparator(path):
    newPath = path.strip()
    if newPath[-1] == os.sep:
        newPath = newPath[:-1]
    return newPath


# File class is used to self determine the file date but the date will come from the EXIF
# data in a JPG if the data can be extracted.
class File:
    def __init__(self, imageFilePath):
        self.imageFilePath = imageFilePath
        self.exif = get_exif_image(imageFilePath)
        # print("self.exif\n", self.exif)
        if self.exif is not None:
            try:
                self.dateExif = self.exif['DateTimeOriginal']
            except:
                self.dateExif = None
        self.GetDate()
        self.dateStr = self.GetDateStr()
        self.year = self.dateStr[:4]

    def GetDate(self):
        if self.exif is None or self.dateExif is None:
            # try to get the date from the file name
            self.date = get_date_from_filename(self.imageFilePath)
            if self.date is None:
                # if that fails, get the date from the file date
                self.date = get_file_date(self.imageFilePath)
        else:
            tmpDate = self.dateExif[:10].split(":")
            # if the date is '-' separated rather than ':' separated
            # then handle that case
            if len(tmpDate) < 3:
                tmpDate = tmpDate[0].split("-")
            print(tmpDate)
            self.date = MakeTimeFromDate(tmpDate[2], tmpDate[1], tmpDate[0])

    def GetDateStr(self):
        # print(self.date)
        return FormatDate(self.date.tm_mday, self.date.tm_mon, self.date.tm_year)

class CopySet:
    def __init__(self, srcDir, dstDir, overwrite=False, preserve_spaces=True, deleteOrig=False):
        self.srcDir = PathWithSeparator(srcDir.strip())
        self.dstDir = PathWithSeparator(dstDir.strip())
        self.GetDstSubDirs()
        self.GetSrcFiles()
        self.GetSrcFilesJpg()
        self.GetSrcFilesOther
        self.overwrite = overwrite
        self.preserve_spaces = preserve_spaces
        self.deleteOrig = deleteOrig

    def GetDstSubDirs(self):
        self.dirs = GetDirs(self.dstDir)
        # print("self.dirs\n", self.dirs)
        return self.dirs

    def GetSrcFiles(self):
        self.files = GetFiles(self.srcDir)
        # print("self.files\n", self.files)
        return self.files

    def GetSrcFilesJpg(self):
        self.srcFilesJpg = [x for x in self.files if x[-4:].lower() == ".jpg"]
        return self.srcFilesJpg

    def GetSrcFilesOther(self):
        self.srcFilesOther = [x for x in self.files if x[-4:].lower() != ".jpg"]
        return self.srcFilesOther

    def GetDestDir(self, date):
        dstDir = self.dstDir + str(date.tm_year) + os.sep + "%04d_%02d_%02d" % (date.tm_year, date.tm_mon, date.tm_mday)
        # print(dstDir + "\n", self.dirs)
        already = [x for x in self.dirs if x.find(dstDir) >= 0]
        if already != []:
            dstDir = already[0]
        print("dstDir", dstDir)
        return dstDir

    def CopyFiles(self):
        print(f"number of files {len(self.files)}")
        for f in self.files:
            print(f)
            fileToCopy = File(f)
            dstDir = self.GetDestDir(fileToCopy.date)
            if self.preserve_spaces:
                destFile = dstDir + os.sep + os.path.basename(f)
            else:
                destFile = dstDir + os.sep + os.path.basename(f).replace(" ", "_")
            if not (os.path.isdir(dstDir)):
                os.makedirs(dstDir)
                print(f"Folder for renaming: {dstDir}")
            if not os.path.isfile(destFile):
                print(f"Copy {os.path.basename(f)} -> {destFile}")
                shutil.copy(f, destFile)
            else:
                if self.overwrite:
                    print(f"Copying over destination file which already exists: {destFile}")
                    shutil.copy(f, destFile)
                else:
                    src_hash = get_hash(f)
                    dst_hash = get_hash(destFile)
                    if src_hash == dst_hash:
                        print(f"Destination file already exists and is the same: {destFile}")
                    else:
                        print(f"Renaming desination file to not overwriting file with the same name: {destFile}")
                        destFile = rename_destfile(destFile)
                        shutil.copy(f, destFile)
            if self.deleteOrig:
                if (os.path.isfile(destFile) and \
                    os.path.getsize(destFile) == os.path.getsize(f)):
                    try:
                        os.remove(f)
                    except:
                        print(f"failed to delete file: {f}")

def main():
    parser = optparse.OptionParser()
    parser.add_option("-s", "--sourcedir", dest="srcdir",
                  help="source directory of files to be copied", metavar="SRCDIR", default="NULL")
    parser.add_option("-d", "--destdir", dest="dstdir",
                  help="destination directory where the files are to be copied", metavar="DSTDIR", default="NULL")
    parser.add_option("-o", action="store_true", dest="overwrite", default=False,
                  help="if the destination file already exists this option will cause the file to be overwritten" )
    parser.add_option("-p", action="store_true", dest="preserve_spaces", default=False,
                  help="this option will stop the file names from having spaces replaced with \"_\"" )
    parser.add_option("-D", action="store_true", dest="deleteOrig", default=False,
                  help="attempt to delete the original file once it has been copied")

    (options, args) = parser.parse_args()

    if not os.path.isdir(options.srcdir) :
        print(f"Error: the source directory does not exist:\n\t{options.srcdir}")
        return 1
    if not os.path.isdir(options.dstdir) :
        print(f"Error: the destination directory does not exist:\n\t{options.dstdir}")
        return 1

    copySet = CopySet(options.srcdir, options.dstdir, options.overwrite, options.preserve_spaces, options.deleteOrig)
    copySet.CopyFiles()
    return 0

if __name__ == '__main__':
    sys.exit(main())

