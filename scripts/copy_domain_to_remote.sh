#!/bin/bash

# Needs some customization, but this will copy a local domain to a remote server

# This just initiates couch's own replication command.  It's pretty quick.
# https://wiki.apache.org/couchdb/Replication
# I have the username and password in environment variables
# ($STAGING_DB_USERNAME and $STAGING_DB_PASSWORD)


PARAMS=`python -c '
import os, json
target = "https://{user}:{password}@commcarehq.cloudant.com/{db_name}".format(
    user=os.environ.get("STAGING_DB_USERNAME"),
    password=os.environ.get("STAGING_DB_PASSWORD"),
    db_name="staging_commcarehq",
)
print json.dumps({
    "source": "performance_db",
    "target": target,
    "http_connections": 4,
    "worker_processes": 2,
    "filter": "domain/all_docs",
    "query_params": {"domain": "bigdomain"},

    # toggle this last param and send a new request to interrupt the replication
    "cancel": True,
})
'`

echo $PARAMS
echo "...POSTing request"
curl \
    -X POST \
    -H "Accept: application/json" \
    -H "Content-Type: application/json; charset=UTF-8" \
    -d "$PARAMS" \
    http://localhost:5984/_replicate
