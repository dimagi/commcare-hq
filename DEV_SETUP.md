Setting up CommCare HQ for Developers
-------------------------------------

Please note that these instructions are targeted toward UNIX-based systems. For Windows, consider using Cygwin or WUBI. Common issues and their solutions can be found at the end of this document.

### (Optional) Copying data from an existing HQ install

If you're setting up HQ on a new computer, you may have an old, functional environment around.  If you don't want to start from scratch, back up your postgres and couch data.

* PostgreSQL
  * Create a pg dump.  You'll need to verify the host IP address:
    `pg_dump -h 0.0.0.0 -U commcarehq commcare_hq > /path/to/backup_hq_db.sql`
* Couchdb
  * From a non-docker install: Copy `/var/lib/couchdb2/`
  * From a docker install: Copy `~/.local/share/dockerhq/couchdb2`.

Save those backups to somewhere you'll be able to access from the new environment.

### Downloading and configuring CommCare HQ

#### Prerequisites

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [Python 2.7](https://www.python.org/downloads/)
- [Pip](https://pip.pypa.io/en/stable/installing/)
- [Virtualenv](https://virtualenv.pypa.io/en/stable/)
- [Virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/#introduction)

##### macOS Notes

- You may need to use `sudo` to for some of the above setup:
```
    $ sudo python get-pip.py
    $ sudo pip install virtualenv
    $ sudo pip install virtualenvwrapper --ignore-installed six
```

- Additional requirements:
  - [Homebrew](https://brew.sh)
  - [libmagic](https://macappstore.org/libmagic) (available via homebrew)
  - [pango](https://www.pango.org/) (available via homebrew)

#### Setup virtualenv

Run the following commands:

    $ source /usr/local/bin/virtualenvwrapper.sh
    $ mkvirtualenv --no-site-packages commcare-hq -p python2.7

#### Clone and setup repo / requirements

Once all the dependencies are in order, please do the following:

    $ git clone https://github.com/dimagi/commcare-hq.git
    $ cd commcare-hq
    $ git submodule update --init --recursive
    $ workon commcare-hq  # if your "commcare-hq" virtualenv is not already activated
    $ setvirtualenvproject  # optional - sets this directory as the project root

Next, install the appropriate requirements (only one is necessary).

* Recommended for those developing CommCareHQ
  * `$ pip install -r requirements/dev-requirements.txt`
* For production environments
  * `$ pip install -r requirements/prod-requirements.txt`
* Minimum required packages
  * `$ pip install -r requirements/requirements.txt`

(If this fails you may need to [install lxml's dependencies](https://stackoverflow.com/a/5178444/8207) or pango.)

Note that once you're up and running, you'll want to periodically re-run these steps, and a few others, to keep your environment up to date. Some developers have found it helpful to automate these tasks. For pulling code, instead of `git pull`, you can run [this script](https://github.com/dimagi/commcare-hq/blob/master/scripts/update-code.sh) to update all code, including submodules. [This script](https://github.com/dimagi/commcare-hq/blob/master/scripts/hammer.sh) will update all code and do a few more tasks like run migrations and update libraries, so it's good to run once a month or so, or when you pull code and then immediately hit an error.

#### Setup for Python 3 (beta)

- Install [Python 3.6](https://www.python.org/downloads/)
    - For OSX, you can [install using Homebrew](http://osxdaily.com/2018/06/13/how-install-update-python-3x-mac/)
    - For Ubuntu 18.04:

          $ sudo apt install python3.6 python3.6-dev

    - For Ubuntu < 18.04:

          $ sudo add-apt-repository ppa:deadsnakes/ppa
          $ sudo apt-get update
          $ sudo apt-get install python3.6

- [Create and activate virtualenv](https://docs.python.org/3/library/venv.html#creating-virtual-environments)
- Install HQ requirements for Python 3.6
    - `$ pip install -r requirements-python3/dev-requirements.txt`

#### Setup localsettings

First create your `localsettings.py` file:

    $ cp localsettings.example.py localsettings.py


Enter `localsettings.py` and do the following:
- Find the `LOG_FILE` and `DJANGO_LOG_FILE` entries. Ensure that the directories for both exist and are writeable. If they do not exist, create them.
- You may also want to add the line `from dev_settings import *` at the top of the file, which includes some useful default settings.

Create the shared directory.  If you have not modified `SHARED_DRIVE_ROOT`, then run:

    $ mkdir sharedfiles

### Set up docker services

Once you have completed the above steps, you can use Docker to build and run all of the service containers.
The steps for setting up Docker can be found in the [docker folder](docker/README.md).

### (Optional) Copying data from an existing HQ install

If you previously created backups of another HQ install's data, you can now copy that to the new install.

* Postgres
  * Make sure postgres is running: `./scripts/docker ps`
  * Make sure `psql` is installed
    * Ubuntu: `$ sudo apt install postgresql postgresql-contrib`
  * Restore the backup: `psql -U commcarehq -h 0.0.0.0 commcarehq < /path/to/backup_hq_db.sql`
* Couchdb
  * Stop couch `./scripts/docker stop couch`
  * Copy the `couchdb2/` dir to `~/.local/share/dockerhq/couchdb2`.
  * Start couch `./scripts/docker start couch`
  * Fire up fauxton to check that the dbs are there: http://0.0.0.0:5984/_utils/

### Set up your django environment

Before running any of the commands below, you should have all of the following running: couchdb, redis, and elasticsearch.
The easiest way to do this is using the docker instructions above.

Populate your database:

    $ ./manage.py sync_couch_views
    $ ./manage.py create_kafka_topics
    $ env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
    $ ./manage.py compilejsi18n

You should run `./manage.py migrate` frequently, but only use the environment
variable CCHQ_IS_FRESH_INSTALL during your initial setup.  It is used to skip a
few tricky migrations that aren't necessary for new installs.

To set up elasticsearch indexes run the following (Ignore warnings
related to Raven for the following two commands.):

    $ ./manage.py ptop_preindex

This will create all of the elasticsearch indexes (that don't already exist) and populate them with any
data that's in the database.

Next, set the aliases of the elastic indices. These can be set by a management command that sets the stored index
names to the aliases.

    $ ./manage.py ptop_es_manage --flip_all_aliases

### Installing Bower

We use bower to manage our javascript dependencies. In order to download the required javascript packages,
you'll need to install `bower` and run `bower install`. Follow these steps to install:

1. If you do not already have npm:

    For Ubuntu: In Ubuntu this is now bundled with NodeJS. An up-to-date version is available on the NodeSource
    repository. Run the following commands:

        $ curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash -
        $ sudo apt-get install -y nodejs

    For macOS: Install with Homebrew:

        $ brew install node

    For others: install [npm](https://www.npmjs.com/)

2. Install bower:

        $ sudo npm -g install bower

3. Run bower with:

        $ bower install


### Install JS-XPATH

This is required for the server side xpath validation. See [package.json](package.json) for exact version.

```
npm install dimagi/js-xpath#v0.0.2-rc1
```

### Using LESS: 2 Options

#### Option 1: Let Client Side Javascript (less.js) handle it for you

This is the setup most developers use. If you don't know which option to use, use this one. It's the simplest to set up and the least painful way to develop: just make sure your `localsettings.py` file has the following set:

```
LESS_DEBUG = True
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
```

The disadvantage is that this is a different setup than production, where LESS files are compressed. It also slows down page load times, compared to compressing offline.


#### Option 2: Compress in Django, caching results in Redis

This is a good option if your local environment is running slowly and you're not doing development in LESS files. Set the following in your `localsettings.py`:

```
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False

COMPRESS_MINT_DELAY = 30
COMPRESS_MTIME_DELAY = 3
COMPRESS_REBUILD_TIMEOUT = 6000
```

The three later settings control how often files are re-compressed; read more about them [here](http://django-compressor.readthedocs.io/en/latest/settings/). In practice, getting files to re-compress whenever you make a change can be tricky; if doing LESS work it's often easier to switch back to option 1 above, compiling client-side.

#### Option 3: Compress OFFLINE, just like production

This mirrors production's setup, but it's really only useful if you're trying to debug issues that mirror production that's related to staticfiles and compressor. For all practical uses, please use Option 1 to save yourself the headache.

Make sure your `localsettings.py` file has the following set:
```
LESS_DEBUG = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

Install LESS and UglifyJS:

1. Install [npm](https://www.npmjs.com/)
2. Install less by running `npm install -g less`
3. Install UglifyJS by running `npm install -g uglify-js@2.6.1`


For all STATICFILES changes (primarily LESS and JavaScript), run:

    $ ./manage.py collectstatic
    $ ./manage.py compilejsi18n
    $ ./manage.py fix_less_imports_collectstatic
    $ ./manage.py compress


#### Formplayer

Formplayer is a Java service that allows us to use applications on the web instead of on a mobile device. 

In `localsettings.py`:
```
FORMPLAYER_URL = 'http://localhost:8010'
LOCAL_APPS += ('django_extensions',)
```

When running HQ, be sure to use `runserver_plus`:
```
python manage.py runserver_plus
```

Then you need to have formplayer running. There are a few options as described below.

##### Running Formplayer in Docker

Please refer to FormPlayer's install instructions under "[Running in Docker](https://github.com/dimagi/formplayer#running-in-docker)".

If you are on Mac, don't bother trying to run this in Docker. There seems to be some kind of bug.
Instead, try running formplayer from a .jar file

##### Running formplayer.jar

Prerequisites:
+ Install Java (left as an exercise for the reader)
+ [Initialize formplayer database](https://github.com/dimagi/formplayer#building-and-running)

To get set up, download the settings file and `formplayer.jar`. You may run this
in the commcare-hq repo root.

```bash
$ curl https://raw.githubusercontent.com/dimagi/formplayer/master/config/application.example.properties -o formplayer.properties
$ curl https://s3.amazonaws.com/dimagi-formplayer-jars/latest-successful/formplayer.jar -o formplayer.jar
```

Thereafter, to run formplayer, navigate to the dir where you installed them
above (probably the repo root), and run:

```bash
$ java -jar formplayer.jar --spring.config.name=formplayer
```

This starts a process in the foreground, so you'll need to keep it open as long
as you plan on using formplayer. If formplayer stops working, you can try
re-fetching it using the same command above. Feel free to add it to your
`hammer` command or wherever.

```bash
$ curl https://s3.amazonaws.com/dimagi-formplayer-jars/latest-successful/formplayer.jar -o formplayer.jar
```

#### Browser Settings

We recommend disabling the cache. In Chrome, go to Dev Tools > Settings > Preferences > Network and check "Disable cache (while DevTools is open)"


Running CommCare HQ
-------------------

Make sure the required services are running (PostgreSQL, Redis, CouchDB, Kafka, Elasticsearch).

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

If database tests are failing because of a `permission denied` error, give your postgres user permissions to create a database.
In the postgres shell, run the following as a superuser: `ALTER USER commcarehq CREATEDB;`

### REUSE DB
To avoid having to run the databse setup for each test run you can specify the `REUSE_DB` environment variable
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

In order to run the javascript tests you'll need to install the required npm packages:

    $ npm install

It's recommended to install grunt globally in order to use grunt from the command line:

    $ npm install -g grunt
    $ npm install -g grunt-cli

In order for the tests to run the __development server needs to be running on port 8000__.

### Running tests from the command line

To run all javascript tests in all the apps:

    $ grunt mocha

To run the javascript tests for a particular app run:

    $ grunt mocha:<app_name> // (e.g. grunt mocha:app_manager)

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

### Continuous javascript testing

By running the `watch` command, it's possible to continuously run the javascript test suite while developing

    $ grunt watch:<app_name>  // (e.g. grunt watch:app_manager)

## Sniffer

You can also use sniffer to auto run the python tests.

When running, sniffer auto-runs the specified tests whenever you save a file
For example, you are working on the `retire` method of `CommCareUser`. You are writing a `RetireUserTestCase`, which you want to run every time you make a small change to the `retire` method, or to the `testCase`. Sniffer to the rescue!

### Sniffer Usage

    $ sniffer -x <test.module.path>[:<TestClass>[.<test_name>]]

In our example, we would run `sniffer -x corehq.apps.users.tests.retire:RetireUserTestCase`

You can also add the regular `nose` environment variables, like `REUSE_DB=1 sniffer -x <test>`

For javascript tests, you can add `--js-` before the javascript app test name, for example:
`sniffer -x --js-app_manager`

You can combine the two to run the javascript tests when saving js files, and run the python tests when saving py files as follows:
`sniffer -x --js-app_manager -x corehq.apps.app_manager:AppManagerViewTest`

### Sniffer Installation instructions
https://github.com/jeffh/sniffer/
(recommended to install pyinotify or macfsevents for this to actually be worthwhile otherwise it takes a long time to see the change)

## Other links

+ [Pre-Docker environment setup instructions](https://github.com/dimagi/commcare-hq/blob/master/PRE_DOCKER_SETUP.md)
+ [Common Issues](https://github.com/dimagi/commcare-hq/blob/master/COMMON_ISSUES.md)
