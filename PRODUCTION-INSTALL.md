CommCare HQ in Production
=========================

This is a complete guide for setting up a production deployment of CommCare HQ
on Ubuntu 16.04 LTS.

Doing this highly discouraged unless you have a specific reason for not using
CommCareHQ.org, because it requires a lot of knowledge and work to set up, let
alone keep up-to-date with new features and bugfixes.

The steps used here are almost identical to those used by india.commcarehq.org,
which is a single-server deployment of CommCare HQ.  For more complicated
deployment needs, contact Dimagi.

Single server setup requires ~4GB RAM minimum.

### Create a new superuser

Log in to your server and create a new superuser to run CommCare HQ and its
helper processes:

    sudo adduser commcarehq

### Install dependencies

As any superuser, run the following commands in order to install all of the
dependencies for HQ.

    sudo apt install postgresql postgresql-server-dev-all couchdb elasticsearch git libffi-dev python-pip virtualenv libxslt1-dev redis-server zookeeper nginx supervisor npm jython
    
Edit `/etc/default/elasticsearch` and uncomment `START_DAEMON=true` line if present.
Then start all required services:

    sudo service postgresql start
    sudo service couchdb start
    sudo service redis start
    sudo service elasticsearch start

### Create a CouchDB database

    curl -X PUT http://localhost:5984/commcarehq

### Create Postgres user and database

    sudo -upostgresql createuser commcarehq
    sudo -upostgresql createdb -O commcarehq commcarehq
    
### Install and start kafka

    wget http://www-eu.apache.org/dist/kafka/0.10.1.0/kafka_2.11-0.10.1.0.tgz
	tar xf kafka_2.11-0.10.1.0.tgz
	cd kafka_2.11-0.10.1.0
    bin/zookeeper-server-start.sh -daemon config/zookeeper.properties
	bin/kafka-server-start.sh -daemon config/server.properties
    
(check for https://kafka.apache.org/downloads for most recent version).

### Set up code checkouts, virtualenvs, and apache config

Login as commcare user and chdir to /home/commcarehq:

    sudo su commcare
    cd ~

Clone CommCare repository with it's dependencies:

    git clone --depth 1 https://github.com/dimagi/commcare-hq.git
	git submodule update --depth 5 --init --recursive
    
(--depth is optional to speedup download if you don't need entire commit history)

Create virtualenv:

    virtualenv .

And install all required packages:

    bin/pip install -r commcare-hq/requirements/requirements.txt -r commcare-hq/requirements/prod-requirements.txt -r commcare-hq/requirements/dev-requirements.txt

### Edit localsettings.py

Copy `/home/commcare-hq/commcare-hq/localsettings.example.py`
to `/home/commcare-hq/commcare-hq/localsettings.py` and edit it to set your Django database
settings.  The relevant part should look something like this:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcarehq', # change this if you used a different database name during createdb
        'USER': 'commcarehq',  # change this if you used a different username
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

COUCH_HTTPS = False
COUCH_SERVER_ROOT = '127.0.0.1:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'
```

Add this required settings at the end of local_settings.py

    from dev_settings import SHARED_DRIVE_ROOT, LOCAL_APPS

Also make sure that the directory or directories containing `LOG_FILE` and
`DJANGO_LOG_FILE` exist and are writeable by the cchq user.

The default localsettings is configured for HTTPS.  We don't currently provide
any support for setting up the SSL certificates required to use HTTPs. Most
things will work without changing these settings, but some things will break if
you have HTTPS configured without an SSL certificate.  In order to avoid this,
edit `localsettings.py` and ensure that `DEFAULT_PROTOCOL` is `http` and not
`https`.

### Sync HQ with databases

While still logged in to the remote server, navigate to `/home/commcarehq/commcare-hq/` and execute
all of the commands from [Set up your django environment](https://github.com/dimagi/commcare-hq#set-up-your-django-environment) 
in the main README, except instead of `./manage.py`, use the full path of the
Python binary for the production virtualenv.  For example:

    /home/commcarehq/bin/python manage.py sync_couch_views
    env CCHQ_IS_FRESH_INSTALL=1 /home/commcarehq/bin/python manage.py migrate --noinput
    /home/commcarehq/bin/python manage.py compilejsi18n
    /home/commcarehq/bin/python manage.py bootstrap mydomain myuser mypassword
    /home/commcarehq/bin/python manage.py create_kafka_topics
    /home/commcarehq/bin/python manage.py ptop_preindex
    /home/commcarehq/bin/python manage.py ptop_es_manage --flip_all_aliases

Note that for the touchforms localsettings, it should correspond to whatever
`env.django_port` is for the environment you added the the fabfile, so
`localhost:8001` in this instance.

### Configure Supervisor

We use [Supervisor](http://supervisord.org/) to start and manage all of the helper
processes for HQ.  Ыe need to configure supervisor with our process
definitions.  To do this, edit `/etc/supervisord.conf` on the remote machine and
replace the last two lines

    ;[include]
    ;files = relative/directory/*.ini

with

    [include]
    files = /home/commcarehq/commcare-hq/services/supervisor/*.conf
    
Create `/home/commcarehq/commcare-hq/services/supervisor`
    
    mkdir -p services/supervisor
    
And populate it with process definitions (assuming you have the commcarehq-ansible repo alongside this one):

    for i in `ls ../commcarehq-ansible/fab/fab/services/templates/`; do /home/commcarehq/bin/python manage.py make_supervisor_conf --conf_file $i --conf_destination services/supervisor --params '{"project":"commcarehq", "environment": "prod", "code_current": "/home/commcarehq/commcare-hq/", "django_bind": "127.0.0.1", "django_port": 8000, "flower_port": 5555, "log_dir":"/tmp", "virtualenv_current":"/home/commcarehq/", "sudo_user": "commcarehq", "celery_params": {"concurrency": 1}}'; done
    
### Install bower & collect static files
    
    npm install bower
    nodejs node_modules/bower/bin/bower install
    /home/commcarehq/bin/python manage.py collectstatic --noinput

### Configure & start web server

Logout from commcare user now and use ordinary superuser account.
Create file /etc/nginx/sites-enabled/commcarehq with following contents:
```
server {
    listen 80;

    server_name yourdomainnamehere;

    client_max_body_size 500m;
    proxy_read_timeout 900;

    location /static/ {
         # fix path as needed
         alias /home/commcarehq/commcare-hq/staticfiles/;
    }

    location / {
        proxy_pass   http://localhost:8000;
    }
}
```

And restart nginx and supervisor:

    sudo service nginx restart
    sudo service supervisor restart
    
### Congrats!

You now have a working production installation of CommCare HQ.  

There may be additional changes necessary to `localsettings.py` in order to
enable certain features like SMS sending.  

See the bottom of the README for instructions on how to enable building CommCare
mobile apps from CommCare HQ (remember to use the full path to the Python binary
for the code_root virtualenv when running manage.py commands).
