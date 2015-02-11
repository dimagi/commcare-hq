#!/bin/sh

docker rm -f commcarehq
docker rm -f redis
docker rm -f couchdb
docker rm -f postgres

#docker rm -f elasticsearch
