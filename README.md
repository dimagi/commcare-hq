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

### Basic Project Structure

+ **submodules/** - submodule reference to the meat of the code (which lives in many other packages, particularly core-hq)
+ **libs/** - Third party libs (presumably python) that you'll need to reference
+ **scripts/** - Any helper scripts you'll want to write to deal with data and or other things.  This stuff should probably run outside the scope of the python environment


Installing CommCare HQ
----------------------

Please note, these instructions are targeted toward UNIX-based systems.


### Requirements

The following are necessary for the basic function of CommCare HQ.

+ `python`
+ `pip`
+ `memcached`
+ **postgres** - [Download postgres here](http://www.enterprisedb.com/products-services-training/pgdownload)
+ **couchdb** - Version 1.0 or greater required - [View installation instructions here](http://wiki.apache.org/couchdb/Installation)
+ **couchdb-lucene** - Instructrions [here](https://github.com/rnewson/couchdb-lucene). Follow instructions "For CouchDB versions prior to 1.1" when applicable, even if you're on a later version of couchdb.

Note on couchdb installation: Using aptitude or apt-get may not install the latest version. See other installation options if version < 1.0 is installed by using this method.

CommCare HQ requires the python package `egenix-mx-base`, but a bug in
`psycopg2` < 2.4.2 makes it difficult to use psycopg2 in a virtualenv if
egenix-mx-base was also installed in a virtualenv.  Since CommCare HQ requires
psycopg 2.4.1, you need to install egenix-mx-base using your operating system's
package manager if it isn't already installed.

#### Configurations for postgres

It is recommended that you create the database **commcarehq** before continuing.


#### Configuration for CouchDB

It is recommended that you create the database **commcarehq** before continuing.


#### Setting up a virtualenv

A virtualenv is not required, but it may make your life easier.

To install:

    sudo pip install virtualenv     # or sudo easy_install virtualenv
    mkdir ~/.virtualenvs/
    virtualenv ~/.virtualenvs/commcare-hq --no-site-packages

Run `source ~/.virtualenvs/commcare-hq/bin/activate` to enter your virtualenv.

`libmagic` is required by `python-magic`, which pip will install automatically. Unfortunately, on Mac OS X, pip doesn't install libmagic itself. To add it, just

     brew install libmagic

#### HQ Bootstrap Requirements

We use our own flavor of [Twitter Bootstrap](http://twitter.github.com/bootstrap/) for our user interface.
Please check the README on our [HQ Bootstrap project page](https://github.com/dimagi/hq-bootstrap) for requirements and instructions.
Most notably, you will need `lessc` and `uglify-js` to compile HQ Bootstrap.


### Install CommCare HQ

Once all the requirements are in order, please do the following:

    git clone git@github.com:dimagi/commcare-hq.git
    cd commcare-hq
    git submodule update --init --recursive
    source ~/.virtualenvs/commcare-hq/bin/activate      # enter your virtualenv if you have one
    pip install -r requirements.txt
    cp localsettings.example.py localsettings.py


#### Edit localsettings.py

Make the necessary edits to localsettings.py (database passwords, email configuration, etc.).
Things to note:

+ Make sure the postgres settings match your expectations (for instance, the postgres user password likely needs to be changed from the ***** in the file)
+ Make sure the CouchDB settings match your expectations
+ Make sure the following lines are correct and that the directories exist and are accessible by your user. Feel free to change the paths to your liking.
    DJANGO_LOG_FILE = "/var/log/datahq/datahq.django.log"
    LOG_FILE = "/var/log/datahq/datahq.log"


#### Set up your django environment

Please make sure you're still in the root directory of commcare-hq and that you are inside the correct virtualenv (if you are using one).

    ./manage.py syncdb
    ./manage.py migrate
    # this will do some basic setup, create a superuser, and create a project
    ./manage.py bootstrap <project-name> <email> <password>
    ./manage.py make_bootstrap # (if it fails add the 'direct-lessc' directive)
    ./manage.py collectstatic

### Don't forget to start up helper processes

#### memcached (a lightweight cacher)

    memcached -d

#### Couch-lucene

    Enable  Lucene settings in  localsettings.py (to view  case list in the  Report section)

#### Celery (asynchronous task scheduler)

   ./manage.py celeryd -v 2 -B -s celery -E


### Get CommCare Binaries

In order to build and download a CommCare mobile app from your instance of CommCare HQ, you need to follow
our instructions for how to download and load CommCare binaries from the Dimagi build server:
https://github.com/dimagi/core-hq/blob/master/corehq/apps/builds/README.md

A Note about requirements.txt
-----------------------------

If an import isn't working it may well be because we aren't specifying all versions in the requirements.txt and you have
an old version. If you figure out this problem and figure out what version we *should* be using, feel free to add it to
requirements.txt as ">=ver.si.on" like so:
    couchdbkit>=0.5.2
(Use == for exact version instead of lower bound.)
