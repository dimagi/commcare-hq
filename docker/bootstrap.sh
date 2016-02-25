#!/usr/bin/env bash

. $(dirname "$0")/_include.sh

echo "CommCareHQ bootstrap script. "

echo "Please enter project name"
read PROJECT_NAME

echo "Please enter the email address for the admin user"
read ADMIN_EMAIL

if [[ ! $email =~ '\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b' ]] ; then
  echo "Bad email. Try again."
  exit 1
fi

echo "Please enter admin password"
read ADMIN_PASSWORD

echo "OK. Starting services and then bootstrapping. "

$DOCKER_DIR/docker-services.sh start

#web_runner run --rm web /mnt/docker/bootstrap_internal.sh $PROJECT_NAME $ADMIN_EMAIL $ADMIN_PASSWORD

#web_runner run --rm --service-ports -e CUSTOMSETTINGS="docker.localsettings_docker" \
#    web python manage.py runserver 0.0.0.0:8000
