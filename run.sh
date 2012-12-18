#!/bin/bash

RUNCMD="run_gunicorn --workers=3"
LOG=gunicorn
XFORMS_PORT=4444

for var in "$@"
do
    if [[ $var = '--werkzeug' ]]; then
        RUNCMD="runserver --werkzeug"
        LOG=werkzeug
    fi
    if [[ $var = '--django' ]]; then
        RUNCMD="runserver"
        LOG=django
    fi
done

PIDS=()

# Asynchronous task scheduler
./manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events >celery.log 2>&1 &
PIDS[0]=$!

# Keeps elasticsearch index in sync
./manage.py run_ptop >run_ptop.log 2>&1 &
PIDS[1]=$!

# only necessary if you want to use CloudCare
killall jython
jython submodules/touchforms-src/touchforms/backend/xformserver.py $XFORMS_PORT >xformserver.log 2>&1 &
PIDS[2]=$!

cleanup() {
    for pid in "${PIDS[@]}"
    do
        kill $pid
    done
}

trap cleanup SIGINT

# run HQ
./manage.py $RUNCMD >$LOG.log 2>&1
