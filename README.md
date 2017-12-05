CommCare HQ
===========

[![Join the chat at https://gitter.im/dimagi/commcare-hq](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/dimagi/commcare-hq?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

https://github.com/dimagi/commcare-hq

[![Build Status](https://travis-ci.org/dimagi/commcare-hq.png)](https://travis-ci.org/dimagi/commcare-hq)

CommCare HQ is a server-side tool to help manage community health workers.
It seamlessly integrates with CommCare mobile and CommCare ODK, as well as
providing generic domain management and form data-collection functionality.

More in depth docs are available on [ReadTheDocs](http://commcare-hq.readthedocs.io/)

### Key Components

+ CommCare application builder
+ OpenRosa compliant XForms designer
+ SMS integration
+ Domain/user/mobile worker management
+ XForms data collection
+ Case management
+ Over-the-air (ota) restore of user and cases
+ Integrated web and email reporting

Contributing
------------
We welcome contributions, see our [CONTRIBUTING.rst](CONTRIBUTING.rst) document for more.

Setting up CommCare HQ for developers
-------------------------------------

Please note that these instructions are targeted toward UNIX-based systems.

### Downloading and configuring CommCare HQ

#### Prerequisites

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [Python 2.7](https://www.python.org/downloads/)
- [Virtualenv](https://virtualenv.pypa.io/en/stable/)
- [Virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/)

#### Setup virtualenv

`mkvirtualenv --no-site-packages commcare-hq -p python2.7`

#### Clone and setup repo / requirements

Once all the dependencies are in order, please do the following:

    $ git clone https://github.com/dimagi/commcare-hq.git
    $ cd commcare-hq
    $ git submodule update --init --recursive
    $ workon commcare-hq  # if your "commcare-hq" virtualenv is not already activated
    $ pip install -r requirements/requirements.txt

There is also a separate collection of Dimagi dev oriented tools that you can install:

    $ pip install -r requirements/dev-requirements.txt

And for production environments you may want:

    $ pip install -r requirements/prod-requirements.txt
    
Note that once you're up and running, you'll want to periodically re-run these steps, and a few others, to keep your environment up to date. Some developers have found it helpful to automate these tasks. For pulling code, instead of `git pull`, you can run [this script](https://github.com/dimagi/commcare-hq/blob/master/scripts/update-code.sh) to update all code, including submodules. [This script](https://github.com/dimagi/commcare-hq/blob/master/scripts/hammer.sh) will update all code and do a few more tasks like run migrations and update libraries, so it's good to run once a month or so, or when you pull code and then immediately hit an error.

#### Setup localsettings

First create your `localsettings.py` file:

    $ cp localsettings.example.py localsettings.py


Enter `localsettings.py` and do the following:
- Find the `LOG_FILE` and `DJANGO_LOG_FILE` entries. Ensure that the directories for both exist and are writeable. If they do not exist, create them.
- Find the `LOCAL_APPS` section and un-comment the line that starts with `'kombu.transport.django'`
- You may also want to add the line `from dev_settings import *` at the top of the file, which includes some useful default settings.

Once you have completed the above steps, you can use Docker to build and run all of the service containers.
The steps for setting up Docker can be found in the [docker folder](docker/README.md).

### Set up your django environment

Before running any of the commands below, you should have all of the following running: couchdb, redis, and elasticsearch.
The easiest way to do this is using the docker instructions below.

Populate your database:

    $ ./manage.py sync_couch_views
    $ env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
    $ ./manage.py compilejsi18n

You should run `./manage.py migrate` frequently, but only use the environment
variable CCHQ_IS_FRESH_INSTALL during your initial setup.  It is used to skip a
few tricky migrations that aren't necessary for new installs.

Create a project. The following command will do some basic setup, create a superuser, and create a project. The
project-name, email, and password given here are specific to your local development environment. Ignore warnings
related to Raven for the following three commands.

    $ ./manage.py bootstrap <project-name> <email> <password>

To set up elasticsearch indexes run the following:

    $ ./manage.py ptop_preindex

This will create all of the elasticsearch indexes (that don't already exist) and populate them with any 
data that's in the database.

Next, set the aliases of the elastic indices. These can be set by a management command that sets the stored index
names to the aliases.

    $ ./manage.py ptop_es_manage --flip_all_aliases

### Installing Bower

We use bower to manage our javascript dependencies. In order to download the required javascript packages,
you'll need to run `./manage.py bower install` and install `bower`. Follow these steps to install:

1. If you do not already have it, install [npm](https://www.npmjs.com/). In Ubuntu this is now bundled
with NodeJS. An up-to-date version is available on the NodeSource repository.

        $ curl -sL https://deb.nodesource.com/setup_5.x | sudo -E bash -
        $ sudo apt-get install -y nodejs

2. Install bower:

        $ `sudo npm -g install bower`

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


#### Option 2: Compress OFFLINE, just like production

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

    $ manage.py collectstatic
    $ manage.py compilejsi18n
    $ manage.py fix_less_imports_collectstatic
    $ manage.py compress


#### CloudCare

To enable CloudCare, ensure that `TOUCHFORMS_API_USER` and
`TOUCHFORMS_API_PASSWORD` in `localsettings.py` are the credentials of the
django admin user you created above (with manage.py bootstrap) and then create
the file `submodules/touchforms-src/touchforms/backend/localsettings.py` with
the following contents:
```
URL_ROOT = 'http://localhost:8000/a/{{DOMAIN}}'
```

#### New CloudCare

A new version of CloudCare has been released. To use this new version, please
refer to the install instructions [here](https://github.com/dimagi/formplayer).

Running CommCare HQ
-------------------

Make sure the required services are running (PostgreSQL, Redis, CouchDB, Kafka, Elasticsearch).

Then run the following separately:

    # run the Django server
    $ ./manage.py runserver 0.0.0.0:8000

    # Keeps elasticsearch index in sync
    $ ./manage.py run_ptop --all
    
    # Setting up the asynchronous task scheduler (only required if you have CELERY_ALWAYS_EAGER=False in settings)
    # For Mac / Linux
    $ ./manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events
    # Windows
    > manage.py celeryd --settings=settings
  
If you want to use CloudCare you will also need to run the Touchforms server.

    # run Touchforms server
    > jython submodules/touchforms-src/touchforms/backend/xformserver.py

Running Formdesigner in Development mode
----------------------------------------
By default, HQ uses vellum minified build files to render form-designer. To use files from Vellum directly, do following

```
# localsettings.py:
VELLUM_DEBUG = "dev"
```

    # simlink your Vellum code to submodules/formdesigner
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
    $ REUSE_DB=reset ./manage.py test corehq.apps.app_manager  # drop the current test DB and create a fresh one
    
See `corehq.tests.nose.HqdbContext` for full description of `REUSE_DB`.

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


Pre-docker dev environment setup instructions (deprecated)
----------------------------------------------------------

### Installing dependencies

For Ubuntu 12.04, download the JDK (version 7) tar.gz from http://www.oracle.com/technetwork/java/javase/downloads/index.html and rename it jdk.tar.gz in the same directory as install.sh.
Run the included `install.sh` script to install all
dependencies, set them up to run at startup, and set up required databases.
Then skip to "Setting up a virtualenv".

Otherwise, install the following software from your OS package manager or the
individual project sites when necessary.

+ Python 2.7 (use 32 bit if you're on Windows see `Alternate steps for Windows` section below)
+ pip  (If you use virtualenv (see below) this will be installed automatically)
+ CouchDB >= 1.0 (1.2 recommended) (install from OS package manager (`sudo apt-get install couchdb`) or [here][couchdb])
   For Mac users
       - use $ brew install couchdb
       - note that when installing erlang, you do NOT need to check out an older version of erlang.rb

+ PostgreSQL >= 9.4 - (install from OS package manager (`sudo apt-get install postgresql`) or [here][postgres])
+ [Elasticsearch][elasticsearch] 1.7.4. In Ubuntu and other Debian derivatives,
  [download the deb package][elasticsearch], install, and then **hold** the version to prevent automatic upgrades:

        $ sudo dpkg -i elasticsearch-1.7.4.deb
        $ sudo apt-mark hold elasticsearch

  On Mac, the following works well:

        $ brew install homebrew/versions/elasticsearch17

+ redis >= 3.0.3 (install from OS package manager (`sudo apt-get install redis-server`) or follow these
  [installation notes][redis])

  On Mac, use:

     	$ brew install redis

+ [Jython][jython] 2.5.3 (optional, only needed for CloudCare). **Note**: CloudCare will _not_ work on 2.7.0 which is
  the default version at jython.org. 2.5.3 is the default version in current versions of Ubuntu
  (`sudo apt-get install jython`) but to be safe you can explicitly set and hold the version with

        $ sudo apt-get install jython=2.5.3
        $ sudo apt-mark hold jython

   If the package is not in apt you will need to install manually: https://wiki.python.org/jython/InstallationInstructions

+ For additional requirements necessary only if you want to modify the default
  JavaScript or CSS styling, see [CommCare HQ Style](https://github.com/dimagi/hqstyle-src).

 [couchdb]: http://wiki.apache.org/couchdb/Installation
 [postgres]: http://www.postgresql.org/download/
 [redis]: https://gist.github.com/mwhite/c0381c5236855993572c
 [elasticsearch]: https://www.elastic.co/downloads/past-releases/elasticsearch-1-7-4
 [jython]: http://jython.org/downloads.html

#### Elasticsearch Configuration (optional)

To run Elasticsearch in an upstart configuration, see [this example](https://gist.github.com/3961323).

To secure Elasticsearch, we recommend setting the listen port to localhost on a
local machine. On a distributed environment, we recommend setting up ssh
tunneled ports for the Elasticsearch port. The supervisor_elasticsearch.conf
supervisor config demonstrates the tunnel creation using autossh.

If working on a network with other Elasticsearch instances that you do not want to be included in your cluster
automatically, set the cluster name to your hostname in /etc/elasticsearch/elasticsearch.yml:
```yaml
cluster.name: <your hostname>
```

#### Kafka Configuration

See [changes_feed README](./corehq/apps/change_feed/README.md).

#### CouchDB Configuration

Start couchdb, and then open http://localhost:5984/_utils/ and create a new database named `commcarehq` and add a user named `commcarehq` with password `commcarehq`.

To set up CouchDB from the command line, create the database:

    $ curl -X PUT http://localhost:5984/commcarehq

And add an admin user:

    $ curl -X PUT http://localhost:5984/_config/admins/commcarehq -d '"commcarehq"'

#### PostgreSQL Configuration

Log in as the postgres user, and create a `commcarehq` user with password `commcarehq`, and `commcarehq` and
`commcarehq_reporting` databases:

    $ sudo su - postgres
    postgres$ createuser -P commcarehq  # When prompted, enter password "commcarehq"
    postgres$ createdb commcarehq
    postgres$ createdb commcarehq_reporting

If these commands give you difficulty, **particularly for Mac users** running Postgres.app, verify that the default
postgres role has been created, and run the same commands without first logging in as the postgres POSIX user:

    $ createuser -s -r postgres  # Create the postgres role if it does not yet exist
    $ createuser -U postgres -P commcarehq  # When prompted, enter password "commcarehq"
    $ createdb -U postgres commcarehq
    $ createdb -U postgres commcarehq_reporting


### Setting up a virtualenv

A virtualenv is not required, but it is very strongly encouraged and will make your life much easier.
If you're on Windows see the section `Alternate steps for Windows` below.
Ubuntu offers a convenient package for virtualenvwrapper, which makes managing and switching
between environments easy:

    $ sudo pip install virtualenvwrapper
    $ mkvirtualenv commcare-hq


### Installing required dev packages

The Python libraries you will be installing in the next step require the following packages. If you are on a mac, there are brew equivalents for some but not all of these packages. You can use 'brew search' to try to find equivalents for those that are available, and don't worry about the others

    $ sudo apt-get install rabbitmq-server \
          libpq-dev \
          libffi-dev \
          libfreetype6-dev \
          libjpeg-dev \
          libtiff-dev \
          libwebp-dev \
          libxml2-dev \
          libxslt-dev \
          python-dev


### Alternate steps for Windows
On Windows it can be hard to compile some of the packages so we recommend installing those from their binary
distributions. Because many of the binary packages are only available in 32bit format you should also make sure
that you have a 32bit version of Python installed.

+ Install 32 bit Python
+ Install [MinGW][mingw] (used to compile some of the packages that don't have binary distributions).
+ Install the following packages from their binaries. If you are using Virtualenv you will need to copy the packages
  files from $PYTHON_HOME/Lib/site-packages to $ENV_HOME/Lib/site-packages. Alternatively you could create your
  Virtualenv with the `--system-site-packages` option.
  + [gevent][gevent]
  + [numpy][numpy]
  + [egenix-mx-base][mxbase]
  + [Pillow][pillow]
  + [psycopg2][psycopg2]
  + [greenlet][greenlet]
+ Install http-parser by adding MinGW/bin to the path and running `pip install http-parser`. You may also need to alter
  $PYTHON_HOME/Lib/distutils/cygwincompiler.py to remove all instances of '-mno-cygwin' which is a depreciated compiler
  option. The http-parser package is required by restkit.
+ Having installed those packages you can comment them out of the requirements/requirements.txt file.
+ Now run

        $ pip install -r requirements/requirements.txt -r requirements/prod-requirements.txt

  as described in the section above.

 [mingw]: http://www.mingw.org/wiki/Getting_Started
 [gevent]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#gevent
 [numpy]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#numpy
 [mxbase]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#mxbase
 [pillow]: https://github.com/python-imaging/Pillow
 [psycopg2]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#psycopg
 [greenlet]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#greenlet
 

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

+ On Mac OS X, if lxml fails to install, ensure that your command line tools are up to date by running `xcode-select --install`.

+ On Mac OS X, if Pillow complains that it can't find freetype, make sure freetype is installed with `brew install freetype`. Then create a symlink with: `ln -s /usr/local/include/freetype2 /usr/local/include/freetype`.

+ If you have an authentication error running `./manage.py migrate` the first
  time, open `pg_hba.conf` (`/etc/postgresql/9.1/main/pg_hba.conf` on Ubuntu)
  and change the line "local all all peer" to "local all all md5".
  
+ If you encounter an error stemming from any Python modules when running `./manage.py sync_couch_views` for the first time, the issue may be that your virtualenv is relying on the `site-packages` directory of your local Python installation for some of its requirements. (Creating your virtualenv with the `--no-site-packages` flag should prevent this, but it seems that it does not always work). You can check if this is the case by running `pip show {name-of-module-that-is-erroring}`. This will show the location that your virtualenv is pulling that module from; if the location is somewhere other than the path to your virtualenv, then something is wrong. The easiest solution to this is to remove any conflicting modules from the location that your virtualenv is pulling them from (as long as you use virtualenvs for all of your Python projects, this won't cause you any issues).

+ On Windows, to get python-magic to work you will need to install the following dependencies.
  Once they are installed make sure the install folder is on the path.
  + [GNUWin32 regex][regex]
  + [GNUWin32 zlib][zlib]
  + [GNUWin32 file][file]

 [regex]: http://sourceforge.net/projects/gnuwin32/files/regex/
 [zlib]: http://sourceforge.net/projects/gnuwin32/files/zlib/
 [file]: http://sourceforge.net/projects/gnuwin32/files/file/

+ On Windows, Touchforms may complain about not having permission to access `tmp`. To solve this make a `c:\tmp` folder.

+ On Windows, if Celery gives this error on startup: `TypeError: 'LazySettings' object is not iterable` apply the
  changes decribed in this bug report comment: https://github.com/celery/django-celery/issues/228#issuecomment-13562642

+ On Amazon EC2's latest Ubuntu Server 14.04 Edition with default source list, `install.sh` may not install elasticsearch due to dependency issues. Use instructions provided in `https://gist.github.com/wingdspur/2026107` to install
