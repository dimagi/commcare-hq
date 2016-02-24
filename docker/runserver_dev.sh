#!/usr/bin/env bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker"


#python manage.py migrate_logs_to_sql
python manage.py migrate
python manage.py run_ptop --all &
jython submodules/touchforms-src/touchforms/backend/xformserver.py &
python manage.py runserver 0.0.0.0:8000
