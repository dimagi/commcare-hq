#!/usr/bin/env -S bash -i
yarn install --frozen-lockfile
./manage.py compilejsi18n
