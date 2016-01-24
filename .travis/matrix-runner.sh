#!/bin/bash
set -ev

server_started() {
    echo "Waiting for server to start"
    for i in `seq 1 15`; do
        printf '.'
        if $(curl --output /dev/null --silent --head --fail http://localhost:8000/); then
            return 0
        fi
        sleep 1
    done

    echo "Server failed to start in allocated time. Exiting."
    return 1
}

if [ "${MATRIX_TYPE}" = "python" ]; then
    coverage run manage.py test --noinput --failfast --traceback --verbosity=2 --testrunner=$TESTRUNNER
elif [ "${MATRIX_TYPE}" = "python-sharded" ]; then
    TESTAPPS="sql_db form_processor couchforms case receiverwrapper"
    coverage run manage.py test --noinput --failfast --traceback --verbosity=2 $TESTAPPS
elif [ "${MATRIX_TYPE}" = "javascript" ]; then
    psql -c 'create database commcarehq' -U postgres
    python manage.py sync_couch_views
    python manage.py migrate --noinput
    python manage.py runserver 8000 &  # Used to run mocha browser tests

    if server_started; then
        grunt mocha
    else
        exit 1
    fi
fi
