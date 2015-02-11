#!/bin/sh

docker run -P --name postgres -e POSTGRES_USER=commcarehq -e POSTGRES_PASSWORD=commcarehq -d postgres
docker run -P --name couchdb -d klaemo/couchdb
docker run -P --name redis   -d redis

echo "Waiting for databases to be initialized"
echo 5
sleep 1
echo 4
sleep 1
echo 3
sleep 1
echo 2
sleep 1
echo 1
sleep 1
echo 0
sleep 1

docker run --rm --link postgres:postgres postgres psql postgres://commcarehq:commcarehq@postgres -c "CREATE DATABASE commcarehq_reporting;"


docker run --rm --link couchdb:couchdb klaemo/couchdb curl -X PUT "http://couchdb:5984/commcarehq"

docker run --rm --link couchdb:couchdb klaemo/couchdb curl -X PUT "http://couchdb:5984/_config/admins/commcarehq" -d \"commcarehq\"


docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis charlesfleche/commcarehq python manage.py syncdb --noinput

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis charlesfleche/commcarehq python manage.py migrate --noinput

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis charlesfleche/commcarehq python manage.py collectstatic --noinput

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis charlesfleche/commcarehq python manage.py bootstrap example example@example.com example


docker run --name commcarehq --link postgres:postgres -p 8000:8000 --link couchdb:couchdb --link redis:redis -d charlesfleche/commcarehq
