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
+ **couchdb** - [Download couchdb here](http://www.couchbase.com/couchbase-server/overview)


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
    cp localsettings.py.example localsettings.py


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
    ./manage.py bootstrap <project-name> <user> <password>
    ./manage.py make_bootstrap # (if it fails add the 'direct-lessc' directive)
    ./manage.py collectstatic

### Don't forget to start up helper processes

#### memcached (a lightweight cacher)

    memcached -d

#### Couch-lucene

    Enable  Lucene settings in  settings.py (to view  case list in the  Report section)

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
