CommCare HQ in Production
=========================

This is a complete guide for setting up a production deployment of CommCare HQ
on Ubuntu 12.04 LTS.  It has only been tested on 32-bit Ubuntu.

Doing this highly discouraged unless you have a specific reason for not using
CommCareHQ.org, because it requires a lot of knowledge and work to set up, let
alone keep up-to-date with new features and bugfixes.

The steps used here are almost identical to those used by india.commcarehq.org,
which is a single-server deployment of CommCare HQ.  For more complicated
deployment needs, contact Dimagi.

### Create a new superuser

Log in to your server and create a new superuser to run CommCare HQ and its
helper processes:

    sudo adduser cchq
    sudo adduser cchq sudo

### Install dependencies

As any superuser, run the following commands in order to install all of the
dependencies for HQ.  As noted at the top of install.sh, you need to download
the tar.gz for the latest JDK 7 for your architecture from
http://www.oracle.com/technetwork/java/javase/downloads/index.html and save the
file as `jdk.tar.gz` in the same directory before running `install.sh`.

    wget https://raw.github.com/dimagi/commcare-hq/master/install.sh
    chmod +x install.sh
    ./install.sh

### Create a CouchDB database

    curl -X PUT http://localhost:5984/commcarehq


### Define a server configuration

Now, switch to your local machine.

First we'll install Git and [Fabric](http://fabfile.org), which lets you manage
your remote deploy by running commands over SSH.

    sudo apt-get install git python-pip
    sudo pip install --upgrade pip
    sudo pip install fabric

You should clone the official CommCare HQ repo located at
https://github.com/dimagi/commcare-hq in order to modify the configuration for
your server.  You can either create a fork on Github or just clone the repo and
maintain a fork locally.

    git clone git://github.com/dimagi/commcare-hq.git
    cd commcare-hq

Next, edit `fabfile.py` to add a new task definition for your server:

```python
@task
def myserver():
    env.environment = 'myserver'
    env.sudo_user = 'cchq'   # change this if you used a different username
    env.hosts = ['<my server ip>']
    env.user = prompt("Username: ", default=env.user)
    env.django_port = '8001'

    _setup_path()

    env.roledefs = {
        'couch': [],
        'pg': [],
        'rabbitmq': [],
        'sofabed': [],
        'django_celery': [],
        'django_app': [],
        'django_public': [],
        'django_pillowtop': [],
        'formsplayer': [],
        'remote_es': [],
        'staticfiles': [],
        'lb': [],
        'deploy': [],

        'django_monolith': ['<my server ip>'],
    }
    env.roles = ['django_monolith']
    env.es_endpoint = 'localhost'
```

Replace both occurrences of `myserver` above with a name for your deployment
and both occurences of `<my server ip>` with the IP address of your server.

You can almost just copy or rename the `def india()` block, but note that it
contains some legacy settings that are removed above.

### Create Postgres user and database

This will create the `cchq` Postgres user (or whatever you have specified as
`env.sudo_user`) and `commcare-hq_myserver` database on the remote server by
SSH-ing in and running the necessary commands.  Be sure to specify the name of
the user you created above when prompted for a username.

   fab myserver create_pg_user
   fab myserver create_pg_db


### Set up code checkouts, virtualenvs, and apache config

This will clone the codebase on the remote server, set up a virtualenv for
all of the necessary Python packages, and install them.  Then it will create and
enable an Apache configuration file that makes Apache handle requests for static
files and delegate the rest to the Django process.

   fab myserver bootstrap

### Edit localsettings.py

Log in to the remote server as the user you created and edit
`/home/cchq/www/myserver/code_root/localsettings.py` to set your Django database
settings.  The relevant part should look something like this:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'commcare-hq_myserver',
        'USER': 'cchq',  # change this if you used a different username
        'PASSWORD': '<password you used for the cchq account>',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

COUCH_SERVER_ROOT = '127.0.0.1:5984'
COUCH_USERNAME = ''
COUCH_PASSWORD = ''
COUCH_DATABASE_NAME = 'commcarehq'
```

Also make sure that the directory or directories containing `LOG_FILE` and
`DJANGO_LOG_FILE` exist and are writeable by the cchq user. 

### Sync HQ with databases

While still logged in to the remote server, navigate to `code_root/` and execute
all of the commands from [Set up your django environment](https://github.com/dimagi/commcare-hq#set-up-your-django-environment) 
in the main README, except instead of `./manage.py`, use the full path of the
Python binary for the production virtualenv.  For example:

    /home/cchq/www/myserver/python_env/bin/python manage.py syncdb --noinput

Note that for the touchforms localsettings, it should correspond to whatever
`env.django_port` is for the environment you added the the fabfile, so
`localhost:8001` in this instance.

Once you have a completed `localsettings.py` (the one in `code_root`, not the
one in `touchforms/backend/` mentioned in the README), be sure to copy it to
`/home/cchq/www/myserver/code_root_preindex/localsettings.py`.

### Start HQ

Back on your local machine, run the following from your local checkout:

    fab myserver deploy

This uses [Supervisor](http://supervisord.org/) to start and manage all of the helper
processes for HQ.

If you have a large amount of data, intend to stay up to date with code changes to
CommCare HQ, and don't want users to have long page load times when they visit
a page that involves a view whose code changed, you may want to run this before
every deploy:

    fab myserver preindex_views

