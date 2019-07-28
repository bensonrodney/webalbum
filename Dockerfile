FROM ubuntu:18.04

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./packages/requirements.txt /usr/src/app/
COPY ./entrypoint/container_entry.sh /usr/src/app/
COPY ./packages/FFVideo-0.0.13.tar.gz /usr/src/app/
COPY ./www/maps-pin.png /usr/src/app/
COPY ./www/error_thumbnail.png /usr/src/app/
COPY ./www/error_view.png /usr/src/app/

# Add some repositories into the apt lists.
RUN echo "deb http://au.archive.ubuntu.com/ubuntu bionic main" >> /etc/apt/sources.list
RUN echo "deb http://archive.ubuntu.com/ubuntu bionic universe" >> /etc/apt/sources.list
RUN echo "deb-src http://archive.ubuntu.com/ubuntu bionic universe" >> /etc/apt/sources.list
RUN apt-get update -q

RUN DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends --fix-missing \
    python python-pip build-essential python-dev ipython \
    libavutil-dev libavcodec-dev libavformat-dev libswscale-dev \
    nginx uwsgi \
    vim

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade FFVideo-0.0.13.tar.gz

COPY nginx/default /etc/nginx/sites-available/default 
COPY uwsgi/webalbum.ini /etc/uwsgi/apps-available/webalbum.ini 

RUN mkdir -p /var/www/cgi-bin/cgi

COPY ./www/webalbum.py /var/www/cgi-bin/cgi/webalbum
COPY ./www/testpage /var/www/cgi-bin/cgi/testpage

EXPOSE 80 

ENTRYPOINT /usr/src/app/container_entry.sh 
