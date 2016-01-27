#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

$DIR/docker-services.sh start

sudo docker-compose -f $DIR/docker-compose-web.yml run web /mnt/docker/bootstrap_internal.sh

sudo docker-compose \
    -f $DIR/docker-compose-web.yml \
    run -e CUSTOMSETTINGS="docker.localsettings-docker" \
    web python manage.py runserver 0.0.0.0:8000

