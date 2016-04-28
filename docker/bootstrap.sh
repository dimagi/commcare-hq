#!/usr/bin/env bash

. $(dirname "$0")/_include.sh

echo "CommCareHQ bootstrap script. "

echo "Please enter project name"
read PROJECT_NAME

echo "Please enter the email address for the admin user"
read ADMIN_EMAIL

char='[[:alnum:]!#\$%&'\''\*\+/=?^_\`{|}~-]'
name_part="${char}+(\.${char}+)*"
domain="([[:alnum:]]([[:alnum:]-]*[[:alnum:]])?\.)+[[:alnum:]]([[:alnum:]-]*[[:alnum:]])?"
begin='(^|[[:space:]])'
end='($|[[:space:]])'

# include capturing parentheses, 
# these are the ** 2nd ** set of parentheses (there's a pair in $begin)
regex="${begin}(${name_part}@${domain})${end}"

if [[ ! $ADMIN_EMAIL =~ $regex ]] ; then
  echo "Bad email '$ADMIN_EMAIL'. Try again."
  exit 1
fi

echo "Please enter admin password"
read ADMIN_PASSWORD

echo "OK. Starting services and then bootstrapping. "

$DOCKER_DIR/docker-services.sh start

web_runner run --rm web /mnt/docker/bootstrap_internal.sh $PROJECT_NAME $ADMIN_EMAIL $ADMIN_PASSWORD

#web_runner run --rm --service-ports -e CUSTOMSETTINGS="docker.localsettings_docker" \
#    web python manage.py runserver 0.0.0.0:8000
