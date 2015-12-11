#!/usr/bin/env bash
# Install pghashlib extension for PostgreSQL

wget https://github.com/markokr/pghashlib/archive/master.zip -O pghashlib.zip
unzip pghashlib.zip
cd pghashlib-master
PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make
sudo PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make install
sudo /etc/init.d/postgresql stop
sudo /etc/init.d/postgresql start $PGVERSION
