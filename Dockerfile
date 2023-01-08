FROM ubuntu:20.04

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./packages/requirements.txt /usr/src/app/
COPY ./entrypoint/container_entry.sh /usr/src/app/
COPY ./www/maps-pin.png /usr/src/app/
COPY ./www/error_thumbnail.png /usr/src/app/
COPY ./www/error_view.png /usr/src/app/

# Add some repositories into the apt lists.
RUN echo "deb http://au.archive.ubuntu.com/ubuntu focal main" >> /etc/apt/sources.list
RUN echo "deb http://archive.ubuntu.com/ubuntu focal universe" >> /etc/apt/sources.list
RUN echo "deb-src http://archive.ubuntu.com/ubuntu focal universe" >> /etc/apt/sources.list
RUN apt-get update -q

RUN DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends --fix-missing \
    python3 \
    python3-pip \
    build-essential \
    python3-dev \
    ipython3 \
    libavutil-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    nginx \
    uwsgi \
    vim

RUN pip3 install --no-cache-dir setuptools
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir moviepy

COPY nginx/default /etc/nginx/sites-available/default
COPY uwsgi/webalbum.ini /etc/uwsgi/apps-available/webalbum.ini

RUN mkdir -p /var/www/cgi-bin/cgi

COPY ./www/webalbum.py /var/www/cgi-bin/cgi/webalbum
COPY ./www/testpage /var/www/cgi-bin/cgi/testpage

EXPOSE 80

ENTRYPOINT /usr/src/app/container_entry.sh
