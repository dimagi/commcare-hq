#!/usr/bin/env bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker"

python manage.py run_ptop --all &
python -m errand_boy.run &
jython submodules/touchforms-src/touchforms/backend/xformserver.py &
python manage.py runserver 0.0.0.0:8000
