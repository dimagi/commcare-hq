#!/usr/bin/env bash

./manage.py makemigrations --noinput --check
if [ $? == 0 ]; then
    # No changes
    echo "migrations ok"
else
    # Changes
    echo -e "\033[0;31mMigrations are missing.  Did you run './manage.py makemigrations'?\033[0m"
    exit 1
fi
