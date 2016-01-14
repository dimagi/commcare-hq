CommCare HQ
===========

[![Join the chat at https://gitter.im/dimagi/commcare-hq](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/dimagi/commcare-hq?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

https://github.com/dimagi/commcare-hq

[![Build Status](https://travis-ci.org/dimagi/commcare-hq.png)](https://travis-ci.org/dimagi/commcare-hq)
[![Test Coverage](https://coveralls.io/repos/dimagi/commcare-hq/badge.svg?branch=master&service=github)](https://coveralls.io/github/dimagi/commcare-hq?branch=master)

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

Contributing
------------
We welcome contributions, see our [CONTRIBUTING.rst](CONTRIBUTING.rst) document for more.

Installing CommCare HQ
----------------------

Please note that these instructions are targeted toward UNIX-based systems.

### Installing dependencies

For Ubuntu 12.04, download the JDK (version 7) tar.gz from http://www.oracle.com/technetwork/java/javase/downloads/index.html and rename it jdk.tar.gz in the same directory as install.sh.
Run the included `install.sh` script to install all
dependencies, set them up to run at startup, and set up required databases.
Then skip to "Setting up a virtualenv". 

Otherwise, install the following software from your OS package manager or the
individual project sites when necessary.

+ Python 2.6 or 2.7 (use 32 bit if you're on Windows see `Alternate steps for Windows` section below)
+ pip  (If you use virtualenv (see below) this will be installed automatically)
+ CouchDB >= 1.0 (1.2 recommended) (install from OS package manager (`sudo apt-get install couchdb`) or [here][couchdb])
   For Mac users
       - use $ brew install couchdb
       - note that when installing erlang, you do NOT need to check out an older version of erlang.rb
      
+ PostgreSQL >= 9.4 - (install from OS package manager (`sudo apt-get install postgresql`) or [here][postgres])
+ [Elasticsearch][elasticsearch] 1.7.4. In Ubuntu and other Debian derivatives,
  [download the deb package][elasticsearch], install, and then **hold** the version to prevent automatic upgrades:

        $ sudo dpkg -i elasticsearch-0.90.13.deb
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

+ For additional requirements necessary only if you want to modify the default
  JavaScript or CSS styling, see [CommCare HQ Style](https://github.com/dimagi/hqstyle-src).

 [couchdb]: http://wiki.apache.org/couchdb/Installation
 [postgres]: http://www.postgresql.org/download/
 [redis]: https://gist.github.com/mwhite/c0381c5236855993572c
 [elasticsearch]: http://www.elasticsearch.org/downloads/0-90-13/
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

A virtualenv is not required, but it may make your life easier. If you're on Windows see the section `Alternate steps
for Windows` below. Ubuntu offers a convenient package for virtualenvwrapper, which makes managing and switching 
between environments easy:

    $ sudo apt-get install virtualenvwrapper
    $ mkvirtualenv cchq


### Installing required dev packages

The Python libraries you will be installing in the next step require the following packages. If you are on a mac, there are brew equivalents for some but not all of these packages. You can use 'brew search' to try to find equivalents for those that are available, and don't worry about the others

    $ sudo apt-get install rabbitmq-server \
          libpq-dev \
          libfreetype6-dev \
          libjpeg-dev \
          libtiff-dev \
          libwebp-dev \
          libxml2-dev \
          libxslt-dev \
          python-dev


### Downloading and configuring CommCare HQ

Once all the dependencies are in order, please do the following:

    $ git clone https://github.com/dimagi/commcare-hq.git
    $ cd commcare-hq
    $ git submodule update --init --recursive
    $ workon cchq  # if your "cchq" virtualenv is not already activated
    $ pip install -r requirements/requirements.txt -r requirements/prod-requirements.txt
    $ cp localsettings.example.py localsettings.py

There is also a separate collection of Dimagi dev oriented tools that you can install:

    $ pip install -r requirements/dev-requirements.txt

Enter localsettings.py and do the following:
    - Find the `LOG_FILE` and `DJANGO_LOG_FILE` entries. Ensure that the directories for both exist 
and are writeable. If they do not exist, create them.
    - You may also want to add the line `from dev_settings import *` at the top of the file, which 
      includes some useful default settings.

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

### Set up your django environment

Populate your database:

    $ ./manage.py sync_couch_views
    $ ./manage.py migrate --noinput
    $ ./manage.py collectstatic --noinput
    $ ./manage.py compilejsi18n

Create a project. The following command will do some basic setup, create a superuser, and create a project. The 
project-name, email, and password given here are specific to your local development environment. Ignore warnings 
related to Raven for the following three commands.

    $ ./manage.py bootstrap <project-name> <email> <password>

To set up elasticsearch indexes, first run (and then kill once you see the "Starting pillow" lines):

    $ ./manage.py run_ptop --all

This will do an initial run of the elasticsearch indexing process, but this will run as a service later. This run 
at least creates the indices for the first time.

Next, set the aliases of the elastic indices. These can be set by a management command that sets the stored index 
names to the aliases.

    $ ./manage.py ptop_es_manage --flip_all_aliases

### Installing Bower

We use bower to manage our javascript dependencies. In order to download the required javascript packages, 
you'll need to run `./manage.py bower install` and install `bower`. Follow these steps to install:

1. Install [npm](https://www.npmjs.com/). In Ubuntu this is now bundled with NodeJS. An up-to-date version is 
   available on the NodeSource repository.

        $ curl -sL https://deb.nodesource.com/setup_5.x | sudo -E bash -
        $ sudo apt-get install -y nodejs

2. Install bower:
 
        $ `sudo npm -g install bower`

3. Run bower with:

        $ bower install


### Using LESS: 3 Options

#### Option 1: Let Client Side Javascript (less.js) handle it for you

Pros:
- Don't need to install anything / manage different less versions.

Cons:
- Slowest option, as caching isn't great and for pages with a lot of imports,
things get REAL slow. Plus if you want to use any javascript compilers like
`coffeescript` in the future, this option won't take care of compiling that.
- Is the furthest away from the production environment possible.

##### How to enable?

Make sure your `localsettings.py` file has the following set:
```
LESS_DEBUG = True
LESS_WATCH = True  # if you want less.js to watch for changes and compile on the fly!
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
```

#### Option 2: Let Django do it as changes are made, cache results in Redis

Pros:
- Faster than client-side compilation
- Closer to production setup (so you find compressor errors as they happen)
- Can use other features of django compressor (for javascript!)

Cons:
- Have to install less versions

##### How to enable?

Make sure your `localsettings.py` file has the following set:
```
LESS_DEBUG = False
LESS_WATCH = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False

COMPRESS_MINT_DELAY = 30
COMPRESS_MTIME_DELAY = 3  # set to higher or lower depending on how often you're editing static files
COMPRESS_REBUILD_TIMEOUT = 6000
```

###### Install LESS

*Note:* The reason why we have TWO versions, rather than one is that the newest
LESS that Twitter Bootstrap 3.0 runs off of is not backwards compatible with
LESS 1.3.1, which Twitter Bootstrap 2.3.2 needs. Since we're running BOTH
simultaneously, we need to have two versions installed.

For LESS 1.3.1 (the native less compiler):

1. Install [npm](https://www.npmjs.com/)
2. Install less@1.3.1 by running `npm install -g less@1.3.1`
3. Make sure `lessc --version` outputs something like 1.3.1 or 1.3.0 as the current version

On production we're using LESS 1.7.3 as the alternate LESS, and this version
for sure works with Bootstrap 3.

Take note of this variable already in `settings.py`
```
LESS_FOR_BOOTSTRAP_3_BINARY = '/opt/lessc/bin/lessc'
```

You can change that to wherever you clone the git repo for 1.7.3, or leave it
as is and follow this accordingly:

1. in `/opt`: `git clone https://github.com/less/less.js.git lessc`
2. In the `lessc` repo `git reset --hard 546bedd3440ff7e626f629bef40c6cc54e658d7e` to go straight to the 1.7.3 
   release. Experiment with newer releases at will.
3. Verify that `/opt/lessc/bin/lessc --version` is around 1.7.3

###### Compressor and Caching

If you're doing a lot of front end work (CSS AND/OR Javascript in Bootstrap 3)
and don't want to guess whether or not the cache picked up your changes, set the
following in `localsettings.py`:
```
COMPRESS_MINT_DELAY = 0
COMPRESS_MTIME_DELAY = 0
COMPRESS_REBUILD_TIMEOUT = 0
```

If you deleted your STATIC files directory, and you're getting 404s on all the
Compressed files, force compression by running:

    $ manage.py compress --force


#### Option 3: Compress OFFLINE, just like production

Pros:
- Closest mirror to production's setup.
- Easy to flip between Option 2 and Option 3

Cons:
- Sucks a lot if you're doing a lot of front end changes.

##### How to enable?

Do everything from Option 2 for LESS compilers setup.

Have the following set in `localsettings.py`:
```
LESS_DEBUG = False
LESS_WATCH = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

Notice that `COMPRESS_MINT_DELAY`, `COMPRESS_MTIME_DELAY`, and
`COMPRESS_REBUILD_TIMEOUT` are not set.

For all STATICFILES changes, run:

    $ manage.py collectstatic
    $ manage.py compilejsi18n
    $ manage.py fix_less_imports_collectstatic
    $ manage.py compress

Option 3 is really only useful if you're trying to debug issues that mirror
production that's related to staticfiles and compressor. For all practical uses
please use Option 2 or Option 1 to save yourself the headache.

#### CloudCare

To enable CloudCare, ensure that `TOUCHFORMS_API_USER` and
`TOUCHFORMS_API_PASSWORD` in `localsettings.py` are the credentials of the
django admin user you created above (with manage.py bootstrap) and then create
the file `submodules/touchforms-src/touchforms/backend/localsettings.py` with
the following contents:
```
URL_ROOT = 'http://localhost:8000/a/{{DOMAIN}}'
```

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

    $ redis-server /path/to/redis.conf
    $ /path/to/unzipped/elasticsearch/bin/elasticsearch &
    $ /path/to/couchdb/bin/couchdb &

Then run the following separately:

    # Setting up the asynchronous task scheduler
    # For Mac / Linux
    $ ./manage.py celeryd --verbosity=2 --beat --statedb=celery.db --events
    # Windows
    > manage.py celeryd --settings=settings

    # Keeps elasticsearch index in sync
    $ ./manage.py run_ptop --all

    # run the Django server
    $ ./manage.py runserver 0.0.0.0:8000

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

Building CommCare Mobile Apps
-----------------------------

In order to build, download, and sync a CommCare mobile app from your instance of
CommCare HQ, you need to follow our [instructions][builds] for how to download
and load CommCare binaries from the Dimagi build server.

 [builds]: https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.md

Running Tests
-------------

To run the standard tests for CommCare HQ, simply run

    $ ./manage.py test

To run a particular test or subset of tests

    $ ./manage.py test <app_name>[.<TestClass>[.<test_name>]]

    # examples
    $ ./manage.py test app_manager
    $ ./manage.py test app_manager.SuiteTest
    $ ./manage.py test app_manager.SuiteTest.test_picture_format

If database tests are failing because of a `permission denied` error, give your postgres user permissions to create a database. 
In the postgres shell, run the following as a superuser: `ALTER USER commcarehq CREATEDB;`

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

    $ sniffer -x <app_name>[.<TestClass>[.<test_name>]]

In our example, we would run `sniffer -x users.RetireUserTestCase`
You should see beautiful green `In good standing` if all is well, otherwise a `Failed - Back to work!` message is displayed. 
If you want to run the whole test suite whenever a file is changed (not recommended), you would run sniffer without the `-x` argument

### Sniffer Installation instructions
https://github.com/jeffh/sniffer/
(recommended to install pyinotify or macfsevents for this to actually be worthwhile otherwise it takes a long time to see the change)

