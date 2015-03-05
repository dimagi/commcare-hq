#!/bin/sh

docker start postgres
docker start couchdb
docker start redis
docker start elasticsearch
docker start commcare-hq
