#!/usr/bin/env bash

. $(dirname "$0")/_include.sh

$DOCKER_DIR/docker-services.sh start

web_runner run --rm web /mnt/docker/bootstrap_internal.sh

web_runner run --rm -e CUSTOMSETTINGS="docker.localsettings_docker" \
    web python manage.py runserver 0.0.0.0:8000
