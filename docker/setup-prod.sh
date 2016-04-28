#!/bin/bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker_prod"

echo "Using $CUSTOMSETTINGS for settings"

clear
echo "Welcome to the CommCareHQ Docker production setup"

echo "Do you want to setup email for production?"
echo "y/N?"
read SETUP_EMAIL

if [ "$SETUP_EMAIL" = "y" ] || [ "$SETUP_EMAIL" = "Y" ]; then
  echo "Please enter the address of the smtp server"
  read EMAIL_HOST
  echo "Please enter the port of the smtp server"
  read EMAIL_PORT
  echo "Please enter the username of the smtp server"
  read EMAIL_HOST_USER
  echo "Please enter the password of the smtp server"
  read EMAIL_HOST_PASSWORD
  echo "Does the server use TLS? [y/n]"
  read EMAIL_USE_TLS
  while [ "$EMAIL_USE_TLS" != "y" ] && [ "$EMAIL_USE_TLS" != "n" ] && [ "$EMAIL_USE_TLS" != "Y" ] && [ "$EMAIL_USE_TLS" != "N" ]; do
      echo "Please reply as 'y' or 'n'"
      read EMAIL_USE_TLS
  done
  if [ "$EMAIL_USE_TLS" == "y" ] || [ "$EMAIL_USE_TLS" == "Y" ]; then
    EMAIL_USE_TLS="True";
  elif [ "$EMAIL_USE_TLS" == "n" ] || [ "$EMAIL_USE_TLS" == "N" ]; then
    EMAIL_USE_TLS="False";
  fi
  echo "Server+user: $EMAIL_HOST_USER@$EMAIL_HOST:$EMAIL_PORT"
  echo "Password: $EMAIL_HOST_PASSWORD"
  echo "Uses TLS? $EMAIL_USE_TLS"

  declare -a VARS=("EMAIL_HOST" "EMAIL_PORT" "EMAIL_HOST_USER" "EMAIL_HOST_PASSWORD" "EMAIL_USE_TLS")

  for i in "${VARS[@]}"
  do
    if [ $(grep -c "$i" localsettings_docker_prod.py) == "0" ]; then
      echo "$i=" >> localsettings_docker_prod.py
    fi
  done

  sed -i.bak "s/EMAIL_HOST=.*/EMAIL_HOST='$EMAIL_HOST'/" localsettings_docker_prod.py
  sed -i.bak "s/EMAIL_PORT=.*/EMAIL_PORT='$EMAIL_PORT'/" localsettings_docker_prod.py
  sed -i.bak "s/EMAIL_HOST_USER=.*/EMAIL_HOST_USER='$EMAIL_HOST_USER'/" localsettings_docker_prod.py
  sed -i.bak "s/EMAIL_HOST_PASSWORD=.*/EMAIL_HOST_PASSWORD='$EMAIL_HOST_PASSWORD'/" localsettings_docker_prod.py
  sed -i.bak "s/EMAIL_USE_TLS=.*/EMAIL_USE_TLS='$EMAIL_USE_TLS'/" localsettings_docker_prod.py
fi

bower prune --production --config.interactive=false
bower update --production --config.interactive=false
python manage.py collectstatic --noinput -v 0
python manage.py fix_less_imports_collectstatic
python manage.py compilejsi18n
python manage.py compress --force -v 0
