#!/usr/bin/env bash

export CUSTOMSETTINGS="docker.localsettings_docker"

./manage.py sync_couch_views
env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
./manage.py compilejsi18n
bower install --config.interactive=false

./manage.py bootstrap demo admin@example.com password
