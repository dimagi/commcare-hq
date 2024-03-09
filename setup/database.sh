#!/usr/bin/env -S bash -i

# Prompt to run containers
echo "Please start up the containers if not already started"
echo "In a separate terminal, please run 'scripts/docker up postgres couch redis elasticsearch5 zookeeper kafka minio'"
echo "We've copied it to the clipboard to make it easy"
echo "When the containers are ready, please type 'ready' below"
echo -n "scripts/docker up postgres couch redis elasticsearch5 zookeeper kafka minio" | xclip -sel clip
read CONTAINERS_READY
if [[ $CONTAINERS_READY != "ready" ]]; then
    echo "Operation terminated. Please re-run when the containers are started"
    exit 1
fi

#read -r DB_NAME DB_USER DB_PASS < <(python -c 'import localsettings; db=localsettings.DATABASES["default"]; print("{} {} {}".format(db["NAME"], db["USER"], db["PASSWORD"]))')
#PGPASSWORD="$DB_PASS" psql -h localhost -p 5432 -U "$DB_USER" -c "CREATE DATABASE commcarehq;"

read -r COUCH_USER COUCH_PASS < <(python -c 'import localsettings; db=localsettings.COUCH_DATABASES["default"]; print("{} {}".format(db["COUCH_USERNAME"], db["COUCH_PASSWORD"]))')

curl -X PUT http://"$COUCH_USER":"$COUCH_PASS"@127.0.0.1:5984/_users
curl -X PUT http://"$COUCH_USER":"$COUCH_PASS"@127.0.0.1:5984/_replicator

./manage.py sync_couch_views
./manage.py create_kafka_topics
env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
./manage.py ptop_preindex
