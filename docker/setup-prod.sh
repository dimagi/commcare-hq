#!/bin/bash

./_include.sh

clear
echo "Welcome to the CommCareHQ Docker production setup"
./create-kafka-topics.sh
./bootstrap.sh
webrunner up
