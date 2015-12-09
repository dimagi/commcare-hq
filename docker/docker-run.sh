#!/bin/sh

docker run -P --name postgres -e POSTGRES_USER=commcarehq -e POSTGRES_PASSWORD=commcarehq -d postgres
docker run -P --name couchdb -d klaemo/couchdb
docker run -P --name redis -d redis
docker run -P --name elasticsearch -d elasticsearch

echo "Waiting for databases to be initialized"
for i in `seq 10 -1 0`
do
  echo $i
  sleep 1
done

docker run --rm --link postgres:postgres postgres psql postgres://commcarehq:commcarehq@postgres -c "CREATE DATABASE commcarehq_reporting;"


docker run --rm --link couchdb:couchdb klaemo/couchdb curl -X PUT "http://couchdb:5984/commcarehq"

docker run --rm --link couchdb:couchdb klaemo/couchdb curl -X PUT "http://couchdb:5984/_config/admins/commcarehq" -d \"commcarehq\"


docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch charlesfleche/commcare-hq python manage.py sync_couch_views

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch charlesfleche/commcare-hq python manage.py migrate --noinput

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch charlesfleche/commcare-hq python manage.py collectstatic --noinput

docker run --rm --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch charlesfleche/commcare-hq python manage.py bootstrap example example@example.com example


docker run --name commcare-hq --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch -p 8000:8000 -e BASE_HOST=`hostname -I | awk '{print $1}'` -d charlesfleche/commcare-hq
