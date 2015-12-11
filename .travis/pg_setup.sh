#!/usr/bin/env bash
# Install extensions for PostgreSQL

set -ev

# install plproxy extension (needed until its added to the travis APT whitelist)
# https://github.com/travis-ci/apt-package-whitelist/issues/2053
sudo apt-get update
sudo apt-get install postgresql-9.1-plproxy postgresql-contrib-$PGVERSION postgresql-server-dev-$PGVERSION

# install pghashlib
sudo /etc/init.d/postgresql stop

wget --quiet https://github.com/markokr/pghashlib/archive/master.zip -O pghashlib.zip
unzip pghashlib.zip
cd pghashlib-master
echo $PGVERSION
PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make
sudo PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make install
sudo /etc/init.d/postgresql stop
sudo /etc/init.d/postgresql start $PGVERSION
