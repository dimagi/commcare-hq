Pre-Docker dev environment setup instructions (deprecated)
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
  + [egenix-mx-base][mxbase]
  + [Pillow][pillow]
  + [psycopg2][psycopg2]
  + [greenlet][greenlet]
+ Having installed those packages you can comment them out of the requirements/requirements.txt file.
+ Now run

        $ pip install -r requirements/requirements.txt -r requirements/prod-requirements.txt

  as described in the section above.

 [mingw]: http://www.mingw.org/wiki/Getting_Started
 [gevent]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#gevent
 [mxbase]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#mxbase
 [pillow]: https://github.com/python-imaging/Pillow
 [psycopg2]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#psycopg
 [greenlet]: http://www.lfd.uci.edu/~gohlke/pythonlibs/#greenlet
