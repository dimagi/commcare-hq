#!/usr/bin/env bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker"

#python manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events 
#python manage.py run_ptop --pillow-key=core
python manage.py run_ptop --all &
jython submodules/touchforms-src/touchforms/backend/xformserver.py &
python manage.py runserver 0.0.0.0:8000
