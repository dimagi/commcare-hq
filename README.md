CommCare HQ
===========

CommCare HQ is a server-side tool to help manage community health workers.
It seamlessly integrates with CommCare mobile and CommCare ODK, as well as
providing generic domain management and form data-collection functionality.

### Key Components

+ CommCare application builder
+ OpenRosa compliant xForms designer
+ SMS integration
+ Domain/user/CHW management
+ Xforms data collection
+ Case management
+ Over-the-air (ota) restore of user and cases
+ Integrated web and email reporting


Installing CommCare HQ
----------------------

Please note that these instructions are targeted toward UNIX-based systems.

### Installing dependencies

For Ubuntu 12.04, you can use the included `install.sh` script to install all
dependencies, set them up to run at startup, and set up required databases.
Then skip to "Setting up a virtualenv". 

Otherwise, install the following software from your OS package manager or the
individual project sites when necessary.

+ Python 2.6 or 2.7
+ pip
+ CouchDB >= 1.0 (1.2 recommended) ([installation instructions][couchdb])
+ PostgreSQL >= 8.4 - (install from OS package manager or [here][postgres])
+ [elasticsearch][elasticsearch] (including Java 7)
+ memcached
+ [Jython][jython] 2.5.2 (optional, only needed for CloudCare)
+ For additional requirements necessary only if you want to modify the default
  JavaScript or CSS styling, see [CommCare HQ Style](https://github.com/dimagi/hqstyle-src).

 [couchdb]: http://wiki.apache.org/couchdb/Installation
 [postgres]: http://jython.org/downloads.html
 [elasticsearch]: http://www.elasticsearch.org/download/
 [jython]: http://jython.org/downloads.html


#### Common issues

+ A bug in psycopg 2.4.1 (a Python package we require) may break CommCare HQ
  when using a virtualenv created with `--no-site-packages` or when the
  `egenix-mx-base` Python package is not already installed. To fix this, install
  `egenix-mx-base` (`sudo apt-get install python-egenix-mxdatetime` on Ubuntu)
  and use `virtualenv --system-site-packages` instead.

+ On Mac OS X, pip doesn't install the `libmagic` dependency for `python-magic`
  properly. To fix this, run `brew install libmagic`.

+ On Mac OS X, libevent may not be installed already, which the Python `gevent` library requires. The error message
  will be a clang error that file `event.h` is not found. To fix this using Homebrew, run `brew install libevent`.

+ To install PIL (Python Image Library) correctly on Ubuntu, you may need to
  follow [these instructions](http://obroll.com/install-python-pil-python-image-library-on-ubuntu-11-10-oneiric/). 
  (If you don't do this, the only thing that won't work is uploading of JPEGs to
  the CommCare Exchange.)

+ If you have an authentication error running `./manage.py syncdb` the first
  time, open `pg_hba.conf` (`/etc/postgresql/9.1/main/pg_hba.conf` on Ubuntu)
  and change the line "local all all peer" to "local all all md5".

#### Configuration for Elasticsearch

To run elasticsearch in an upstart configuration, see [this example](https://gist.github.com/3961323).

To secure elasticsearch, we recommend setting the listen port to localhost on a
local machine. On a distributed environment, we recommend setting up ssh
tunneled ports for the elasticsearch port. The supervisor_elasticsearch.conf
supervisor config demonstrates the tunnel creation using autossh.


### Setting up a virtualenv

A virtualenv is not required, but it may make your life easier.

    sudo pip install virtualenv
    mkdir ~/.virtualenvs/
    virtualenv ~/.virtualenvs/commcare-hq --no-site-packages

### Downloading and configuring CommCare HQ

Once all the dependencies are in order, please do the following:

    git clone git@github.com:dimagi/commcare-hq.git
    cd commcare-hq
    git submodule update --init --recursive
    source ~/.virtualenvs/commcare-hq/bin/activate      # enter your virtualenv if you have one
    pip install -r requirements/requirements.txt -r requirements/prod-requirements.txt
    cp localsettings.example.py localsettings.py

Then, edit localsettings.py and ensure that your Postgres, CouchDB, email, and
log file settings are correct, as well as any settings required by any other
functionality you want to use, such as SMS sending and Google Analytics.

Ensure that the directories for `LOG_FILE` and `DJANGO_LOG_FILE` exist and are
writeable.


### Set up your django environment

    # you may have to run syncdb twice to get past a transient error
    ./manage.py syncdb --noinput
    ./manage.py migrate --noinput
    ./manage.py collectstatic --noinput

    # this will do some basic setup, create a superuser, and create a project
    ./manage.py bootstrap <project-name> <email> <password>

    # To set up elasticsearch indexes, first run:
    ./manage.py run_ptop

    # Note the hqcases_<long_string> part in the output of the above
    # command, and run:
    curl -XPOST 'http://localhost:9200/_aliases' -d \
        '{ "actions": [ {"add": {"index": "hqcases_<long_string>", "alias": "hqcases"}}]}'

    # If run_ptop didn't output anything like hqcases_<long_string>, run 
    curl -GET 'http://localhost:9200/_status?pretty=true' and find it near the
    top of the output
    # 
    # Any potential future changes to the HQ code that change the case index
    # mapping type for elasticsearch require you to repeat this step. This
    # process will be improved.

To enable CloudCare, ensure that `TOUCHFORMS_API_USER` and
`TOUCHFORMS_API_PASSWORD` in `localsettings.py` are the credentials of the
django admin user you created above and then create the file
`submodules/touchforms-src/touchforms/backend/localsettings.py` with the
following contents:

    URL_ROOT = 'http://localhost:8000/a/{{DOMAIN}}'


Running CommCare HQ
-------------------

### Development

If your installation didn't set up the helper processes required by CommCare HQ
to automatically run on system startup, you need to run them manually:

    memcached -d &
    /path/to/unzipped/elasticsearch/bin/elasticsearch &
    /path/to/couchdb/bin/couchdb &

Then run the following separately:

    # Asynchronous task scheduler
    ./manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events

    # Keeps elasticsearch index in sync
    ./manage.py run_ptop

    # only necessary if you want to use CloudCare
    jython submodules/touchforms-src/touchforms/backend/xformserver.py

    ./manage.py runserver --werkzeug

### Production

We use [Fabric](http://fabfile.org) for deploy automation and
[supervisor](http://supervisord.org) for process control.  For a production
deploy of CommCare HQ, follow these steps:

1. Create a new user on your server

        adduser cchq
        # add your user as a sudoer by running `sudo visudo` and copying the
        # root=ALL line


2. Fork the Github repo and add an environment definition like
   [this](https://github.com/dimagi/commcare-hq/commit/875092d54988ce8b56dac8755acc82c1a98ceb72),
   changing `env.home` to '/home/cchq', `env.environment` to whatever name you want,
   `env.sudo_user` to 'cchq', and `env.hosts` and
   `env.roledefs['django_monolith']` to contain the IP of your server.

3. Clone your forked Github repo to your local machine.

4. Enter a virtualenv with fabric installed or just do

        sudo pip install fabric

5. Clone repo and set up virtualenvs and other production-specific configs

        fab <my_environment> bootstrap

6. Run the commands from "Set up your django environment" above, except instead
   of ./manage.py, use

       /home/cchq/www/worldbank/code_root/python_env/bin/python manage.py 

7. Deploy
    
        # reindexes CouchDB views so they can be swapped with the old ones
        # without long wait times the next time they are hit
        fab <my_environment> preindex_views

        # check out latest code and restart server processes 
        fab <my_environment> deploy


Building CommCare Mobile Apps
-----------------------------

In order to build and download a CommCare mobile app from your instance of
CommCare HQ, you need to follow our [instructions][builds] for how to download
and load CommCare binaries from the Dimagi build server.

 [builds]: https://github.com/dimagi/core-hq/blob/master/corehq/apps/builds/README.md
