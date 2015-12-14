#!/usr/bin/env bash
# Install extensions for PostgreSQL

set -ev

# ------------------------------------------------------------------------------
# Remove PostgreSQL and all its files
# ------------------------------------------------------------------------------
sudo service postgresql stop
sudo apt-get remove postgresql libpq-dev libpq5 postgresql-client-common postgresql-common -qq --purge -y
sudo rm -rf /var/lib/postgresql

sudo apt-get update -qq

# ------------------------------------------------------------------------------
# Install PostgreSQL (always install from PostgreSQL Apt repository)
# ------------------------------------------------------------------------------
sudo apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install -y -qq postgresql-$PGVERSION postgresql-contrib-$PGVERSION postgresql-server-dev-$PGVERSION

# Install packages
# ------------------------------------------------------------------------------
echo "Installing packages ... this may take some time."
sudo apt-get install -y postgresql-$PGVERSION-plproxy postgresql-contrib-$PGVERSION postgresql-server-dev-$PGVERSION

# Build and compile pghashlib
wget --quiet https://github.com/markokr/pghashlib/archive/master.zip -O pghashlib.zip
unzip pghashlib.zip
cd pghashlib-master
echo $PGVERSION
PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make
! sudo PG_CONFIG=/usr/lib/postgresql/$PGVERSION/bin/pg_config make install
sudo ldconfig

# ------------------------------------------------------------------------------
# Restart once
# ------------------------------------------------------------------------------
sudo /etc/init.d/postgresql restart
