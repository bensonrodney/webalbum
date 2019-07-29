webalbum
========

Dynamic web based photo album served inside a docker container for easy deployment.

For a quick start run the following commands in the Ubuntu shell (lines starting with `#` are just comments):
```
# install docker
sudo apt-get install docker.io

# add your user to the 'docker' group
sudo usermod -aG docker $USER

# you should log out and back in at this point for the group membership changes to take effect
./build.sh

# create a new config file for you Google Maps API key
cp ./config/webalbum.conf.example ./config/webalbum.conf
# you should now edit the new file ./config/webalbum.conf to contain your
# Google Maps API key (you'll have to google how to obtain one as the instructions
# change over time)

# start up a new container
./run.sh -p TCP_PORT -s PHOTO_SOURCE_DIRECTORY -d DATA_DIR
```
where:
 - TCP_PORT is the http port to serve the album on (default is 80) 
 - PHOTO_SOURCE_DIRECTORY is the directory containing all the photos and videos (can contain subfolders, in fact if your ablum is large enough it should ;) )
 - DATA_DIR is a read/write directory used for caching thumbnails and view-sized images.


There's also a script called photocopy.py which can be used to take many unorganised photos
and videos (with the appropriate file name convention, such as those created by Samsung
phones) into organised directories in your original source album. The directory structure
used is `$ALBUM_ROOT/YYYY/YYYY-mm-dd` where `YYYY` is the year, `mm` is the month and `dd` is the
day of the month.

This cgi based web album which dynamically creates it's pages as you view it - no maintenance when
source images change

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
on platforms other than Ubuntu. For this reason I've made it available as a docker container. 

I'm thinking of adding a search capability which will help find folders or images from within
the source images.

Enjoy. 
