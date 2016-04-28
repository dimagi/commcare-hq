#!/usr/bin/env bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker_prod"
export COMMCAREHQ_BASE_HOST=$@

echo "Using $CUSTOMSETTINGS for settings"

#python manage.py migrate_logs_to_sql
touch /tmp/errand-boy
python -m errand_boy.run & 
python manage.py run_ptop --all &
jython submodules/touchforms-src/touchforms/backend/xformserver.py &
/vendor/bin/gunicorn --bind 0.0.0.0:8000 -c deployment/gunicorn/gunicorn_conf.py  deployment.gunicorn.commcarehq_wsgi:application
