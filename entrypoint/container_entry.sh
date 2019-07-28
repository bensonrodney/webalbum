#!/bin/bash

# use supervisord for this later
cp /usr/src/app/*.png /var/www/webalbum/
mkdir -p /var/www/webalbum/thumbnails
mkdir -p /var/www/webalbum/view
nginx
uwsgi /etc/uwsgi/apps-available/webalbum.ini

