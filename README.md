webalbum
========

cgi based web album which dynamically creates it's pages as you view it - no maintenance when
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
