# Set up for running CommCareHQ test cases via Travis-CI

# Prerequisite apt packages
cat requirements/apt-packages.txt | xargs sudo apt-get install -qq

# Python environment (it is a snapshotted VM so I don't think we have to bother w/ virtualenv)
sudo pip install -r requirements/dev-requirements.txt

# CouchDB

# Postgres 
sudo -u postgres psql --file="commcare-hq-test-setup.psql"

# Set up the DBs via Django
python manage.py syncdb --noinput
python manage.py migrate --noinput

