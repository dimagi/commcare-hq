#!/bin/bash


export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker_prod"

echo "Using $CUSTOMSETTINGS for settings"

clear
echo "Welcome to the CommCareHQ Docker production setup"
bower prune --production --config.interactive=false 
bower update --production --config.interactive=false 
python manage.py collectstatic --noinput -v 0 
python manage.py fix_less_imports_collectstatic 
python manage.py compilejsi18n 
python manage.py compress --force -v 0

