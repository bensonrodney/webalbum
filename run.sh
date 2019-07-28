#!/bin/bash

src_dir="/mnt/data/photos"
data_dir="/mnt/data/webalbum_data"
tcp_port="80"
auto_restart="--restart always"

function usage() {
    cat << EOF

Usage:
    ${0} [-s PHOTO_SOURCE_DIR] [-d DATA_DIR] [-p TCP_PORT] [-n]

    where:
        -s PHOTO_SOURCE_DIR : specifies the source directory containing the
            source images and videos (default is ${src_dir}).

        -d DATA_DIR : specifies the cache directory of thumbnails, medium sized
            images and geotag files (default is ${data_dir}).

        -p TCP_PORT : the port used to serve the HTTP web album (default
            is ${tcp_port}).

        -n : turn off auto restart

EOF
    if [[ -z ${1// } ]] ; then
        exit 1
    else
        exit $1
    fi
}

while getopts "hs:d:p:n" o; do
    case "${o}" in
        h)
            usage 0
            ;;
        s)
            src_dir=${OPTARG}
            ;;
        d)
            data_dir=${OPTARG}
            ;;
        p)
            tcp_port=${OPTARG}
            ;;
        n)
            auto_restart=""
            ;;
        *)
            echo -e "Unknown option!\n\n"
            usage 1
            ;;
    esac
done
shift $((OPTIND-1))

if [[ ! -f ./config/webalbum.conf ]] ; then
    cat <<EOF
No ./config/webalbum.conf file!

Create one by copying ./config/webalbum.conf.example to
./config/webalbum.conf and editing it with your Google Maps
API key.

EOF
    exit 1
fi

if [[ -z ${src_dir// } ]] ; then
    echo -e "Empty source directory specified.\n\n"
    usage 1
fi

if [[ -z ${data_dir// } ]] ; then
    echo -e "Empty data directory specified.\n\n"
    usage 1
fi

docker run ${auto_restart} \ 
    --rm -p ${tcp_port}:80 \
	-v $(pwd)/config:/etc/webalbum:ro \
	-v ${src_dir}:/mnt/originalphotos:ro \
	-v ${data_dir}:/var/www/webalbum \
	-it webalbum

