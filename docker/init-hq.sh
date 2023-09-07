#!/bin/sh

if ! ./manage.py first_superuser > /dev/null
then
    export CCHQ_IS_FRESH_INSTALL=1
    ./manage.py sync_couch_views
    ./manage.py migrate --noinput
    ./manage.py compilejsi18n
    ./manage.py create_kafka_topics
    printf 'Passw0rd!\nPassw0rd!\n' | ./manage.py make_superuser admin@example.com
else
    ./manage.py migrate --noinput
fi
