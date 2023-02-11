#!/usr/bin/env python3

import logging
from logging import handlers
import os
import sys
from PIL import Image
from PIL.ExifTags import TAGS

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


def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "Model":
                return value
    return None


def get_camera_from_image(imgfile):
    try:
        img = Image.open(imgfile)
        return get_exif_data(img)
    except Image.UnidentifiedImageError as exc:
        logger.error(f"{imgfile}: {str(exc)}")


def find_files(path, filt=None):
    filteredfiles = []
    for dir, dirs, files in os.walk(path):
        filteredfiles += [dir+os.sep+f for f in files if f.lower().endswith(".jpg")]
    filteredfiles.sort()
    return filteredfiles


def find_cam_files(path, cam_search):
    camfiles = []
    for f in find_files(path):
        camera = get_camera_from_image(f)
        if (camera is not None) and (cam_search.lower() in camera.lower()):
            camfiles.append((f, camera))
    return camfiles


def list_cam_files(path, cam_search, limit=50):
    camfiles = find_cam_files(path, cam_search)
    if (limit > 0) and (len(camfiles) > limit):
        camfiles = camfiles[-limit+1:]
    print("path: {}".format(path))
    if len(camfiles) < 1:
        print("No files found for camera search '{}'".format(cam_search))
    else:
        for f, camera in camfiles:
            print("{:<100} {}".format(f, camera))


def get_cams_list(path):
    cams = set()
    for f in find_files(path):
        camera = get_camera_from_image(f)
        if (camera is not None):
            cams.add(camera)
    return list(cams)


def list_cams(path):
    cams = get_cams_list(path)
    print("path: {}".format(path))
    if len(cams) < 1:
        print("No camera info found")
    else:
        print('\n'.join(cams))


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-p', '--path', dest='path', default='/mnt/hddData/photos',
                      help='path to search in')
    parser.add_option('-c', '--camera', dest='camera', default=None,
                      help="camera to search for")
    parser.add_option('-l', '--list', dest='list', default=False, action='store_true',
                      help='list the cameras found')
    parser.add_option('-L', '--limit', dest='limit', default=50,
                      help='limit the list to the last LIMIT number of results, default 50, 0 = no limit')
    (options, args) = parser.parse_args()

    if options.list:
        list_cams(options.path)
        return 0

    if options.camera is None:
        print("TODO: USAGE\n\n")
        return 1

    list_cam_files(options.path, options.camera, limit=options.limit)
    return 0


if __name__ == '__main__':
    sys.exit(main())
