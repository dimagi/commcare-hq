Setting up CommCare HQ for Developers
-------------------------------------

This document describes setting up a development environment for working on
CommCare HQ. Such an environment is not suitable for real projects. Production
environments should be deployed and managed [using
commcare-cloud](https://dimagi.github.io/commcare-cloud/)

These instructions are for Mac or Linux computers. For Windows, consider using
an Ubuntu virtual machine.

Common issues and their solutions can be found at the end
of this document.

### (Optional) Copying data from an existing HQ install

If you're setting up HQ on a new computer, you may have an old, functional
environment around.  If you don't want to start from scratch, back up your
Postgres and Couch data.

* PostgreSQL
  * Create a pg dump.  You'll need to verify the host IP address:

        $ pg_dump -h 0.0.0.0 -U commcarehq commcarehq > /path/to/backup_hq_db.sql

* CouchDB
  * From a non-Docker install: Copy `/var/lib/couchdb2/`
  * From a Docker install: Copy `~/.local/share/dockerhq/couchdb2`.

Save those backups to somewhere you'll be able to access from the new environment.

### Downloading and configuring CommCare HQ

#### Prerequisites

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

      $ sudo apt install git

- [Python 3.6](https://www.python.org/downloads/) and `python-dev`. In Ubuntu
  you will also need to install the modules for pip and venv explicitly.

      $ sudo apt install python3-dev python3-pip python3-venv

- [Virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/#introduction)

      $ sudo python3 -m pip install virtualenvwrapper

- Requirements of Python libraries, if they aren't already installed.

      $ sudo apt install libpango1.0-0 libncurses-dev libxml2-dev libxslt1-dev libpq-dev


##### macOS Notes

- You may need to use `sudo` to for some of the above setup:

      $ sudo python get-pip.py
      $ sudo pip install virtualenvwrapper --ignore-installed six

- Additional requirements:
  - [Homebrew](https://brew.sh)
  - [libmagic](https://macappstore.org/libmagic) (available via homebrew)
  - [pango](https://www.pango.org/) (available via homebrew)


#### Set up virtual environment

1. Set the `WORKON_HOME` environment variable to the path where you keep
   your virtual environments. If you don't already have a home for your
   virtual environments, ~/venv is not a bad choice:

       $ export WORKON_HOME=$HOME/venv
       $ mkdir -p $WORKON_HOME

1. Create a virtual environment for CommCare HQ. "commcare-hq" is a good
   name, but naming it "cchq" might save you some typing in the future:

       $ python3 -m venv $WORKON_HOME/cchq

1. Ubuntu no longer ships with Python 2 and its Python binary is named
   "python3" to avoid ambiguity. You may need to tell virtualenvwrapper
   where to find Python:

       $ export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3

1. Enable virtualenvwrapper:

       $ source /usr/local/bin/virtualenvwrapper.sh

1. You will want to add virtualenvwrapper settings to your startup
   script, say, ~/.bashrc, or ~/.zshrc. For example:

       $ cat <<EOF >> ~/.bashrc
       export WORKON_HOME=\$HOME/venv
       export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
       source /usr/local/bin/virtualenvwrapper.sh
       EOF

1. Activate your virtual environment:

       $ workon cchq


#### Clone repo and install requirements

Once all the dependencies are in order, please do the following:

    $ git clone https://github.com/dimagi/commcare-hq.git
    $ cd commcare-hq
    $ git submodule update --init --recursive
    $ setvirtualenvproject  # optional - sets this directory as the project root

Next, install the appropriate requirements (only one is necessary).

* Recommended for those developing CommCare HQ

      $ pip install -r requirements/dev-requirements.txt

* For production environments

      $ pip install -r requirements/prod-requirements.txt

* Minimum required packages

      $ pip install -r requirements/requirements.txt

(If this fails you may need to [install lxml's dependencies](https://stackoverflow.com/a/5178444/8207) or pango.)

Note that once you're up and running, you'll want to periodically re-run these steps, and a few others, to keep your environment up to date. Some developers have found it helpful to automate these tasks. For pulling code, instead of `git pull`, you can run [this script](https://github.com/dimagi/commcare-hq/blob/master/scripts/update-code.sh) to update all code, including submodules. [This script](https://github.com/dimagi/commcare-hq/blob/master/scripts/hammer.sh) will update all code and do a few more tasks like run migrations and update libraries, so it's good to run once a month or so, or when you pull code and then immediately hit an error.

#### Setup localsettings

First create your `localsettings.py` file:

    $ cp localsettings.example.py localsettings.py


Enter `localsettings.py` and do the following:
- Find the `LOG_FILE` and `DJANGO_LOG_FILE` entries. Ensure that the directories for both exist and are writeable. If they do not exist, create them.
- You may also want to add the line `from dev_settings import *` at the top of the file, which includes some useful default settings.

Create the shared directory.  If you have not modified `SHARED_DRIVE_ROOT`, then run:

    $ mkdir sharedfiles


### Set up Docker services

Once you have completed the above steps, you can use Docker to build
and run all of the service containers. There are detailed instructions
for setting up Docker in the [docker folder](docker/README.md). But the
following should cover the needs of most developers:

    $ sudo apt install docker.io
    $ pip install docker-compose
    $ sudo adduser $USER docker

Log in as yourself again, to activate membership of the "docker" group:

    $ su - $USER

Ensure the Docker service is running:

    $ sudo service docker status

Bring up the Docker containers for the services you probably need:

    $ scripts/docker up postgres couch redis elasticsearch zookeeper kafka minio

or, to detach and run in the background, use the `-d` option:

    $ scripts/docker up -d postgres couch redis elasticsearch zookeeper kafka minio


### (Optional) Copying data from an existing HQ install

If you previously created backups of another HQ install's data, you can now copy that to the new install.

* Postgres
  * Make sure Postgres is running:

        $ ./scripts/docker ps

  * Make sure `psql` is installed: (Ubuntu)

        $ sudo apt install postgresql postgresql-contrib

  * Restore the backup:

        $ psql -U commcarehq -h 0.0.0.0 commcarehq < /path/to/backup_hq_db.sql

* CouchDB
  * Stop Couch:

        $ ./scripts/docker stop couch

  * Copy the `couchdb2/` dir to `~/.local/share/dockerhq/couchdb2`.
  * Start Couch

        $ ./scripts/docker start couch

  * Fire up Fauxton to check that the dbs are there: http://0.0.0.0:5984/_utils/


### Set up your Django environment

Before running any of the commands below, you should have all of the following
running: CouchDB, Redis, and Elasticsearch.
The easiest way to do this is using the Docker instructions above.

Populate your database:

    $ ./manage.py sync_couch_views
    $ ./manage.py create_kafka_topics
    $ env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
    $ ./manage.py compilejsi18n

You should run `./manage.py migrate` frequently, but only use the environment
variable CCHQ_IS_FRESH_INSTALL during your initial setup.  It is used to skip a
few tricky migrations that aren't necessary for new installs.

To set up elasticsearch indexes run the following:

    $ ./manage.py ptop_preindex

This will create all of the elasticsearch indexes (that don't already exist) and populate them with any
data that's in the database.

Next, set the aliases of the elastic indices. These can be set by a management command that sets the stored index
names to the aliases.

    $ ./manage.py ptop_es_manage --flip_all_aliases

### Installing Bower

We use Bower to manage our JavaScript dependencies. In order to download the required JavaScript packages,
you'll need to install `bower` and run `bower install`. Follow these steps to install:

1. If you do not already have npm:

    For Ubuntu: In Ubuntu this is now bundled with NodeJS. An up-to-date version is available on the NodeSource
    repository. Run the following commands:

        $ curl -sL https://deb.nodesource.com/setup_10.x | sudo -E bash -
        $ sudo apt-get install -y nodejs

    For macOS: Install with Homebrew:

        $ brew install node

    For others: install [npm](https://www.npmjs.com/)

2. Install Bower:

        $ sudo npm -g install bower

3. Run Bower with:

        $ bower install


### Install JS-XPATH

This is required for the server side xpath validation. See [package.json](package.json) for exact version.

```
npm install dimagi/js-xpath#v0.0.2-rc1
```

### Using LESS: 2 Options

#### Option 1: Let Client Side Javascript (less.js) handle it for you

This is the setup most developers use. If you don't know which option to use, use this one. It's the simplest to set up and the least painful way to develop: just make sure your `localsettings.py` does not contain `COMPRESS_ENABLED` or `COMPRESS_OFFLINE` settings (or has them both set to `False`).

The disadvantage is that this is a different setup than production, where LESS files are compressed.

#### Option 2: Compress OFFLINE, just like production

This mirrors production's setup, but it's really only useful if you're trying to debug issues that mirror production that's related to staticfiles and compressor. For all practical uses, please use Option 1 to save yourself the headache.

Make sure your `localsettings.py` file has the following set:
```
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

For all STATICFILES changes (primarily LESS and JavaScript), run:

    $ ./manage.py collectstatic
    $ ./manage.py compilejsi18n
    $ ./manage.py fix_less_imports_collectstatic
    $ ./manage.py compress


#### Formplayer

Formplayer is a Java service that allows us to use applications on the web instead of on a mobile device. 

In `localsettings.py`:
```
FORMPLAYER_URL = 'http://localhost:8080'
LOCAL_APPS += ('django_extensions',)
```

When running HQ, be sure to use `runserver_plus`:

    $ ./manage.py runserver_plus 0.0.0.0:8000

Then you need to have Formplayer running.

Prerequisites:
+ Install Java

      $ sudo apt install default-jre

+ [Initialize Formplayer database](https://github.com/dimagi/formplayer#building-and-running).
  The password for the "commcarehq" user is in the localsettings.py file
  in the `DATABASES` dictionary.

      $ sudo apt install postgresql-client
      $ createdb formplayer -U commcarehq -h localhost

To get set up, download the settings file and `formplayer.jar`. You may run this
in the commcare-hq repo root.

    $ curl https://raw.githubusercontent.com/dimagi/formplayer/master/config/application.example.properties -o application.properties
    $ curl https://s3.amazonaws.com/dimagi-formplayer-jars/latest-successful/formplayer.jar -o formplayer.jar

Thereafter, to run Formplayer, navigate to the dir where you installed them
above (probably the repo root), and run:

    $ java -jar formplayer.jar

This starts a process in the foreground, so you'll need to keep it open as long
as you plan on using Formplayer.

To keep Formplayer up to date with the version used in production, you can add
the `curl` commands above to your `hammer` command, or whatever script you use
for updating your dev environment.


#### Browser Settings

We recommend disabling the cache. In Chrome, go to Dev Tools > Settings > Preferences > Network and check "Disable cache (while DevTools is open)"


Running CommCare HQ
-------------------

Make sure the required services are running (PostgreSQL, Redis, CouchDB, Kafka, Elasticsearch).

    $ ./manage.py check_services

Some of the services listed there aren't necessary for very basic operation, but it can give you a good idea of what's broken.

Then run the following separately:

    # run the Django server
    $ ./manage.py runserver 0.0.0.0:8000

    # Keeps elasticsearch index in sync
    $ ./manage.py run_ptop --all

    # Setting up the asynchronous task scheduler (only required if you have CELERY_TASK_ALWAYS_EAGER=False in settings)
    $ celery -A corehq worker -l info

Create a superuser for your local environment

    $ ./manage.py make_superuser <email>

Running Formdesigner in Development mode
----------------------------------------
By default, HQ uses vellum minified build files to render form-designer. To use files from Vellum directly, do following

```
# localsettings.py:
VELLUM_DEBUG = "dev"
```

    # symlink your Vellum code to submodules/formdesigner
    $ ln -s absolute/path/to/Vellum absolute/path/to/submodules/formdesigner/


Airflow
-------

It is usually not required to have a local airflow environment running.

However, if you do need to get setup on Airflow (which is used to back some reporting infrastructure)
you can follow the instructions in the [pipes repository](https://github.com/dimagi/pipes/).


Running Tests
-------------

To run the standard tests for CommCare HQ, simply run

    $ ./manage.py test

To run a particular test or subset of tests

    $ ./manage.py test <test.module.path>[:<TestClass>[.<test_name>]]

    # examples
    $ ./manage.py test corehq.apps.app_manager
    $ ./manage.py test corehq.apps.app_manager.tests.test_suite:SuiteTest
    $ ./manage.py test corehq.apps.app_manager.tests.test_suite:SuiteTest.test_picture_format

    # alternate: file system path
    $ ./manage.py test corehq/apps/app_manager
    $ ./manage.py test corehq/apps/app_manager/tests/test_suite.py:SuiteTest
    $ ./manage.py test corehq/apps/app_manager/tests/test_suite.py:SuiteTest.test_picture_format

If database tests are failing because of a `permission denied` error, give your
Postgres user permissions to create a database.
In the Postgres shell, run the following as a superuser:

    # ALTER USER commcarehq CREATEDB;

### REUSE DB
To avoid having to run the database setup for each test run you can specify the
`REUSE_DB` environment variable
which will use an existing test database if one exists:

    $ REUSE_DB=1 ./manage.py test corehq.apps.app_manager

Or, to drop the current test DB and create a fresh one

    $ ./manage.py test corehq.apps.app_manager --reusedb=reset

See `corehq.tests.nose.HqdbContext` for full description
of `REUSE_DB` and `--reusedb`.

### Running tests by tag
You can run all tests with a certain tag as follows:

    $ ./manage.py test --attr=tag

Available tags:

  * all_backends: all tests decorated with `run_with_all_backeds`

See http://nose.readthedocs.io/en/latest/plugins/attrib.html for more details.

### Running only failed tests
See https://github.com/nose-devs/nose/blob/master/nose/plugins/testid.py

## Javascript tests

### Setup

In order to run the JavaScript tests you'll need to install the required npm packages:

    $ npm install

It's recommended to install grunt globally in order to use grunt from the command line:

    $ npm install -g grunt
    $ npm install -g grunt-cli

In order for the tests to run the __development server needs to be running on port 8000__.

### Running tests from the command line

To run all JavaScript tests in all the apps:

    $ grunt test

To run the JavaScript tests for a particular app run:

    $ grunt test:<app_name> // (e.g. grunt test:app_manager)

To list all the apps available to run:

    $ grunt list


### Running tests from the browser

To run tests from the browser (useful for debugging) visit this url:

```
http://localhost:8000/mocha/<app_name>
```

Occasionally you will see an app specified with a `#`, like `app_manager#b3`. The string after `#` specifies that the test uses an alternate configuration. To visit this suite in the browser go to:

```
http://localhost:8000/mocha/<app_name>/<config>  // (e.g. http://localhost:8000/mocha/app_manager/b3)
```

## Sniffer

You can also use sniffer to auto run the Python tests.

When running, sniffer auto-runs the specified tests whenever you save a file
For example, you are working on the `retire` method of `CommCareUser`. You are writing a `RetireUserTestCase`, which you want to run every time you make a small change to the `retire` method, or to the `testCase`. Sniffer to the rescue!

### Sniffer Usage

    $ sniffer -x <test.module.path>[:<TestClass>[.<test_name>]]

In our example, we would run 

    $ sniffer -x corehq.apps.users.tests.retire:RetireUserTestCase`

You can also add the regular `nose` environment variables, like `REUSE_DB=1 sniffer -x <test>`

For JavaScript tests, you can add `--js-` before the JavaScript app test name, for example:

    $ sniffer -x --js-app_manager

You can combine the two to run the JavaScript tests when saving js files, and
run the Python tests when saving py files as follows:

    $ sniffer -x --js-app_manager -x corehq.apps.app_manager:AppManagerViewTest

### Sniffer Installation instructions
https://github.com/jeffh/sniffer/
(recommended to install pywatchman or macfsevents for this to actually be worthwhile otherwise it takes a long time to see the change)

## Other links

+ [Common Issues](https://github.com/dimagi/commcare-hq/blob/master/COMMON_ISSUES.md)
