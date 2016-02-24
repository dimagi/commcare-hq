#!/usr/bin/env bash

export C_FORCE_ROOT="true"
export CUSTOMSETTINGS="docker.localsettings_docker"

#python manage.py migrate_logs_to_sql
bower install --allow-root --config.interactive=false
python manage.py collectstatic
python manage.py fix_less_imports_collectstatic
python manage.py run_ptop --all &
jython submodules/touchforms-src/touchforms/backend/xformserver.py &
/vendor/bin/gunicorn --bind 0.0.0.0:8000 -c deployment/gunicorn/gunicorn_conf.py  deployment.gunicorn.commcarehq_wsgi:application


