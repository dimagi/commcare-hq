CommCare HQ
===========

https://github.com/dimagi/commcare-hq

[![Build Status](https://travis-ci.org/dimagi/commcare-hq.png)](https://travis-ci.org/dimagi/commcare-hq)
[![Test coverage](https://coveralls.io/repos/dimagi/commcare-hq/badge.png?branch=master)](https://coveralls.io/r/dimagi/commcare-hq)

CommCare HQ is a server-side tool to help manage community health workers.
It seamlessly integrates with CommCare mobile and CommCare ODK, as well as
providing generic domain management and form data-collection functionality.

More in depth docs are available on [ReadTheDocs](http://commcare-hq.readthedocs.org/en/latest/)

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

For Ubuntu 12.04, download the JDK tar.gz from http://www.oracle.com/technetwork/java/javase/downloads/index.html and rename it jdk.tar.gz in the same directory as install.sh.
Run the included `install.sh` script to install all
dependencies, set them up to run at startup, and set up required databases.
Then skip to "Setting up a virtualenv". 

Otherwise, install the following software from your OS package manager or the
individual project sites when necessary.

+ Python 2.6 or 2.7 (use 32 bit if you're on Windows see `Alternate steps for Windows` section below)
+ pip
+ CouchDB >= 1.0 (1.2 recommended) ([installation instructions][couchdb])
+ PostgreSQL >= 8.4 - (install from OS package manager or [here][postgres])
+ [elasticsearch][elasticsearch] (including Java 7).
  - The version we run is `Version: 0.90.5, JVM: 1.7.0_05`.
  - `brew install homebrew/versions/elasticsearch090` works well on mac
+ memcached
+ redis >= 2.2.12 ([installation notes](https://gist.github.com/mwhite/c0381c5236855993572c))
+ [Jython][jython] 2.5.2 (optional, only needed for CloudCare)
+ For additional requirements necessary only if you want to modify the default
  JavaScript or CSS styling, see [CommCare HQ Style](https://github.com/dimagi/hqstyle-src).

 [couchdb]: http://wiki.apache.org/couchdb/Installation
 [postgres]: http://www.postgresql.org/download/
 [elasticsearch]: http://www.elasticsearch.org/downloads/0-90-13/
 [jython]: http://jython.org/downloads.html

#### Elasticsearch Configuration (optional)

To run elasticsearch in an upstart configuration, see [this example](https://gist.github.com/3961323).

To secure elasticsearch, we recommend setting the listen port to localhost on a
local machine. On a distributed environment, we recommend setting up ssh
tunneled ports for the elasticsearch port. The supervisor_elasticsearch.conf
supervisor config demonstrates the tunnel creation using autossh.

#### CouchDB Configuration

Open http://localhost:5984/_utils/ and create a new database named `commcarehq` and add a user named `commcarehq` with password `commcarehq`.

To set up CouchDB from the command line

Create the database:

    curl -X PUT "http://localhost:5984/commcarehq

Add the required user:

    curl -X PUT "http://localhost:5984/_config/users/commcarehq" -d \"commcarehq\"

#### PostgreSQL Configuration

    createuser -U postgres commcarehq
    createdb -U postgres commcarehq
    createdb -U postgres commcarehq_reporting


### Setting up a virtualenv

A virtualenv is not required, but it may make your life easier. If you're on Windows see the section `Alternate steps
for Windows` below.

    sudo pip install virtualenv
    mkdir ~/.virtualenvs/
    virtualenv ~/.virtualenvs/commcare-hq --no-site-packages

### Downloading and configuring CommCare HQ

Once all the dependencies are in order, please do the following:

    git clone git@github.com:dimagi/commcare-hq.git
    cd commcare-hq
    git submodule update --init --recursive
    source ~/.virtualenvs/commcare-hq/bin/activate      # enter your virtualenv if you have one
    mkdir pip_cache
    pip install --download-cache pip_cache -r requirements/requirements.txt -r requirements/prod-requirements.txt
    cp localsettings.example.py localsettings.py

There is also a separate collection of Dimagi dev oriented tools that you can install:

  pip install -r requirements/dev-requirements.txt

Then, edit localsettings.py and ensure that your Postgres, CouchDB, email, and
log file settings are correct, as well as any settings required by any other
functionality you want to use, such as SMS sending and Google Analytics.

Ensure that the directories for `LOG_FILE` and `DJANGO_LOG_FILE` exist and are
writeable.

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
+ Now run `pip install -r requirements/requirements.txt -r requirements/prod-requirements.txt` as described in the
  section above.

 [mingw]: http://www.mingw.org/wiki/Getting_Started
 [gevent]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#gevent
 [numpy]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#numpy
 [mxbase]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#mxbase
 [pillow]: https://github.com/python-imaging/Pillow
 [psycopg2]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#psycopg
 [greenlet]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#greenlet

### Set up your django environment

    # you may have to run syncdb twice to get past a transient error
    ./manage.py syncdb --noinput
    ./manage.py migrate --noinput
    ./manage.py collectstatic --noinput

    # This will do some basic setup, create a superuser, and create a project.
    # The project-name, email, and password given here are specific to your
    # local development environment.
    ./manage.py bootstrap <project-name> <email> <password>

    # To set up elasticsearch indexes, first run (and then kill once you see the
    "Starting pillow" lines):
    ./manage.py run_ptop --all
    # This will do an initial run of the elasticsearch indexing process, but this will run as a
    # service later. This run at least creates the indices for the first time.
    
    # Next, set the aliases of the elastic indices. These can be set by a management command
    # that sets the stored index names to the aliases.

    ./manage.py ptop_es_manage --flip_all_aliases


### Optional for using Django Compressor: Install lessc for compiling less files

    1. Install node and alongside it npm (eg, on a mac: `brew install node`)
    2. Install less@1.7.1 with npm `npm install -g less@1.3.1`
    3. Make sure `lessc --version` runs and outputs 1.3.1 as the current version

    If you don't do this, all the .less files should compile on the fly with
    less.js in your browser (for development purposes ONLY).


To enable CloudCare, ensure that `TOUCHFORMS_API_USER` and
`TOUCHFORMS_API_PASSWORD` in `localsettings.py` are the credentials of the
django admin user you created above (with manage.py bootstrap) and then create
the file `submodules/touchforms-src/touchforms/backend/localsettings.py` with
the following contents:

    URL_ROOT = 'http://localhost:8000/a/{{DOMAIN}}'

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

+ If you have an authentication error running `./manage.py syncdb` the first
  time, open `pg_hba.conf` (`/etc/postgresql/9.1/main/pg_hba.conf` on Ubuntu)
  and change the line "local all all peer" to "local all all md5".

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

Running CommCare HQ
-------------------

If your installation didn't set up the helper processes required by CommCare HQ
to automatically run on system startup, you need to run them manually:

    redis-server /path/to/redis.conf
    memcached -d &
    /path/to/unzipped/elasticsearch/bin/elasticsearch &
    /path/to/couchdb/bin/couchdb &

Then run the following separately:

    # MacOS Asynchronous task scheduler
    ./manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events
    # Windows
    > manage.py celeryd --settings=settings

    # Keeps elasticsearch index in sync
    ./manage.py run_ptop --all

    # run the Django server
    ./manage.py runserver 0.0.0.0:8000

If you want to use CloudCare you will also need to run the Touchforms server and be running a multi-threaded

    # run Touchforms server
    > jython submodules/touchforms-src/touchforms/backend/xformserver.py

    # On Mac / Linux use Gunicorn as the multi-threaded server
    ./manage.py run_gunicorn -w 3 --bind 0.0.0.0:8000

    # on Windows use CherryPy
    > manage.py runcpserver port=8000

If you run a development server on a port other than 8000, you need to go into
the Django Admin and change the Site object to reflect this, otherwise certain
features like links in emails and CloudCare may behave incorrectly.

Building CommCare Mobile Apps
-----------------------------

In order to build and download a CommCare mobile app from your instance of
CommCare HQ, you need to follow our [instructions][builds] for how to download
and load CommCare binaries from the Dimagi build server.

 [builds]: https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.md

Running Tests
-------------

To run the standard tests for CommCare HQ, simply run

    ./manage.py test

To run a particular test or subset of tests

    ./manage.py test <app_name>[.<TestClass>[.<test_name>]]

    # examples
    ./manage.py test app_manager
    ./manage.py test app_manager.SuiteTest
    ./manage.py test app_manager.SuiteTest.test_picture_format

To run the selenium tests, you first need to install the
[ChromeDriver](https://code.google.com/p/selenium/wiki/ChromeDriver).

The tests for CloudCare currently expect the "Basic Tests" app from the
`corpora` domain on CommCareHQ.org to be installed in the same domain locally.

Make sure to edit the selenium user credentials in `localsettings.py`.  Then run

    ./manage.py seltest
