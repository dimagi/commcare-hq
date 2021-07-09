## Setting up CommCare HQ for Developers

This document describes setting up a development environment for working on
CommCare HQ. Such an environment is not suitable for real projects. Production
environments should be deployed and managed [using
commcare-cloud](https://dimagi.github.io/commcare-cloud/)

These instructions are for Mac or Linux computers. For Windows, consider using
an Ubuntu virtual machine.

Once your environment is up and running, bookmark the [dev FAQ](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md)
for common issues encountered in day-to-day HQ development.

### (Optional) Copying data from an existing HQ install

If you're setting up HQ on a new computer, you may have an old, functional
environment around.  If you don't want to start from scratch, back up your
Postgres and Couch data.

- PostgreSQL
  - Create a pg dump.  You'll need to verify the host IP address:

    ```sh
    pg_dump -h 0.0.0.0 -U commcarehq commcarehq > /path/to/backup_hq_db.sql
    ```

- CouchDB
  - From a non-Docker install: Copy `/var/lib/couchdb2/`.
  - From a Docker install: Copy `~/.local/share/dockerhq/couchdb2`.

- Shared Directory
  - If you are following the default instructions, copy the `sharedfiles`
    directory from the HQ root folder, otherwise copy the directory referenced
    by `SHARED_DRIVE_ROOT` in `localsettings.py`

Save those backups to somewhere you'll be able to access from the new environment.

### Downloading and configuring CommCare HQ

#### Prerequisites

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

    ```sh
    sudo apt install git
    ```

- [Python 3.6](https://www.python.org/downloads/) and `python-dev`. In Ubuntu
  you will also need to install the modules for pip and venv explicitly.

    ```sh
    sudo apt install python3.6-dev python3-pip python3-venv
    ```

- [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/#introduction)

    ```sh
    sudo python3 -m pip install virtualenvwrapper
    ```

- Requirements of Python libraries, if they aren't already installed.

  - **Linux**:

    ```sh
    sudo apt install libncurses-dev libxml2-dev libxmlsec1-dev libxmlsec1-openssl libxslt1-dev libpq-dev pkg-config
    ```

  - **macOS**:

    ```sh
    brew install libmagic libxmlsec1 libxml2 libxslt
    ```

- Java (JDK 8)

  - **Linux**: install `default-jre` via apt:

      ```sh
      sudo apt install default-jre
      ```

  - **macOS**: install [Java SE Development Kit 8][oracle_jdk8] from Oracle
    (requires signing in with an Oracle account to download).

    Example setup using jenv:

      1. Download and install Oracle JDK 8 from [oracle.com downloads page][oracle_jdk8].
      2. Install jenv

          ```sh
          brew install jenv
          ```

      3. Configure your shell (Bash folks use `~/.bashrc` instead of `~/.zshrc` below):

          ```sh
          echo 'export PATH="$HOME/.jenv/bin:$PATH"' >> ~/.zshrc
          echo 'eval "$(jenv init -)"' >> ~/.zshrc
          ```

      4. Add JDK 8 to jenv:

          ```sh
          jenv add $(/usr/libexec/java_home -v 1.8)
          ```

      5. Verify jenv config:

          ```sh
          jenv doctor
          ```

  [oracle_jdk8]: https://www.oracle.com/java/technologies/javase/javase-jdk8-downloads.html


- PostgreSQL

  Installing the `psycopg2` package on macOS requires postgres binaries.

  Executing postgres commands (e.g. `psql`, `createdb`, `pg_dump`, etc) requires
  installing postgres. These commands are explicitly necessary, but having the
  ability to run them may be useful.

  - **Linux** (optional) install the `postgresql-client` package:

    ```sh
    sudo apt install postgresql-client
    ```

  - **macOS** (required) the postgres binaries can be installed via Homebrew:

    ```sh
    brew install postgresql
    ```

    Possible alternative to installing postgres (from [this SO answer](https://stackoverflow.com/a/39800677)).
    Prior to `pip install` commands (outlined later in this doc):

    ```sh
    xcode-select --install
    export LDFLAGS="-I/usr/local/opt/openssl/include -L/usr/local/opt/openssl/lib"
    ```


##### macOS Notes

- [Homebrew](https://brew.sh) (this doc depends heavily on it).

- Install pip:

    ```sh
    sudo python get-pip.py
    ```

- If using `virtualenvwrapper` instead of `pyenv`:

    ```sh
    sudo pip install virtualenvwrapper --ignore-installed six
    ```

- For downloading Python 3.6 consider:

  - Using [pyenv](https://github.com/pyenv/pyenv-installer)
  - Using Homebrew with this [brew formula](https://gist.github.com/SamuelMarks/0ceaaf6d3de12b6408e3e67aae80ae3b)

- For using Java, consider:
  - Using [jenv](https://github.com/jenv/jenv)
  - Trying Homebrew's [openjdk@8 formula](https://formulae.brew.sh/formula/openjdk)
    instead of Oracle's Java via PKG install.


##### xmlsec

`xmlsec` is a `pip` dependency that will require some non-`pip`-installable
packages. The above notes should have covered these requirements for linux and
macOS, but if you are on a different platform or still experiencing issues,
please see [`xmlsec`'s install notes](https://pypi.org/project/xmlsec/).


#### Set up virtual environment

1. Set the `WORKON_HOME` environment variable to the path where you keep
   your virtual environments. If you don't already have a home for your
   virtual environments, ~/venv is not a bad choice:

    ```sh
    export WORKON_HOME=$HOME/venv
    mkdir -p $WORKON_HOME
    ```

1. Create a virtual environment for CommCare HQ. "commcare-hq" is a good
   name, but naming it "hq" might save you some typing in the future:

    ```sh
    python3 -m venv $WORKON_HOME/hq
    ```

1. Ubuntu no longer ships with Python 2 and its Python binary is named
   "python3" to avoid ambiguity. You may need to tell virtualenvwrapper
   where to find Python:

    ```sh
    export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
    ```

1. Enable virtualenvwrapper:

    ```sh
    source /usr/local/bin/virtualenvwrapper.sh
    ```

1. You will want to add virtualenvwrapper settings to your startup
   script, say, ~/.bashrc, or ~/.zshrc. For example:

    ```sh
    $ cat <<EOF >> ~/.bashrc
    export WORKON_HOME=~/venv
    export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
    source /usr/local/bin/virtualenvwrapper.sh
    EOF
    ```

1. Activate your virtual environment:

    ```sh
    workon hq
    ```

1. Ensure your vitualenv `pip` is up-to-date:

    ```sh
    python3 -m pip install --upgrade pip
    ```


#### Clone repo and install requirements

1. Once all the dependencies are in order, please do the following:

    ```sh
    git clone https://github.com/dimagi/commcare-hq.git
    cd commcare-hq
    git submodule update --init --recursive
    git-hooks/install.sh
    setvirtualenvproject  # optional - sets this directory as the project root
    ```

1. Next, install the appropriate requirements (only one is necessary).

  - Recommended for those developing CommCare HQ

    ```sh
    pip install -r requirements/dev-requirements.txt
    ```

  - Recommended for developers or others with custom requirements. Use this `pip
    install ...` workflow for initial setup only. Then use commands in
    `local.in`.

    ```sh
    cp requirements/local.in.sample requirements/local.in
    # customize requirements/local.in as desired
    pip install -r requirements/local.in
    ```

  - For production environments

    ```sh
    pip install -r requirements/prod-requirements.txt
    ```

  - Minimum required packages

    ```sh
    pip install -r requirements/requirements.txt
    ```

    (If this fails you may need to [install the prerequisite system dependencies](#prerequisites).)

Note that once you're up and running, you'll want to periodically re-run these
steps, and a few others, to keep your environment up to date. Some developers
have found it helpful to automate these tasks. For pulling code, instead of `git pull`,
you can run [this script](https://github.com/dimagi/commcare-hq/blob/master/scripts/update-code.sh)
to update all code, including submodules. [This script](https://github.com/dimagi/commcare-hq/blob/master/scripts/hammer.sh)
will update all code and do a few more tasks like run migrations and update
libraries, so it's good to run once a month or so, or when you pull code and
then immediately hit an error.


#### Setup localsettings

First create your `localsettings.py` file:

```sh
cp localsettings.example.py localsettings.py
```

Open `localsettings.py` and do the following:

- Find the `LOG_FILE` and `DJANGO_LOG_FILE` entries. Ensure that the directories
  for both exist and are writeable. If they do not exist, create them.

Create the shared directory.  If you have not modified `SHARED_DRIVE_ROOT`, then
run:

```sh
mkdir sharedfiles
```


### Set up Docker services

Once you have completed the above steps, you can use Docker to build and run all
of the service containers. There are detailed instructions for setting up Docker
in the [docker folder](docker/README.md). But the following should cover the
needs of most developers.


1. Install docker packages.

    **Mac**: see [Install Docker Desktop on Mac](https://docs.docker.com/docker-for-mac/install/)
    for docker installation and setup.

    **Linux**:

    ```sh
    # install docker
    sudo apt install docker.io

    # ensure docker is running
    systemctl is-active docker || sudo systemctl start docker
    # add your user to the `docker` group
    sudo adduser $USER docker
    # login as yourself again to activate membership of the "docker" group
    su - $USER

    # re-activate your virtualenv (with your venv tool of choice)
    # (virtualenvwrapper)
    workon hq

    # or (pyenv)
    pyenv activate hq

    # or (virtualenv)
    source $WORKON_HOME/hq/bin/activate
    ```

1. Install the `docker-compose` python library.

    ```sh
    pip install docker-compose
    ```

1. Ensure the elasticsearch config files are world-readable (their containers
   will fail to start otherwise).

    ```sh
    chmod 0644 ./docker/files/elasticsearch*.yml
    ```

1. Bring up the docker containers.

    In either of the following commands, omit the `-d` option to keep the
    containers attached in the foreground.

    ```sh
    ./scripts/docker up -d
    # Optionally, start only specific containers.
    ./scripts/docker up -d postgres couch redis elasticsearch2 zookeeper kafka minio formplayer
    ```

1. If you are planning on running Formplayer from a binary or source, stop the
   formplayer container to avoid port collisions.

    ```sh
    ./scripts/docker stop formplayer
    ```


### (Optional) Copying data from an existing HQ install

If you previously created backups of another HQ install's data, you can now copy
that to the new install.

- Postgres
  - Make sure Postgres is running:

    ```sh
    ./scripts/docker ps
    ```

  - Make sure `psql` is installed: (Ubuntu)

    ```sh
    sudo apt install postgresql postgresql-contrib
    ```

  - Restore the backup:

    ```sh
    psql -U commcarehq -h 0.0.0.0 commcarehq < /path/to/backup_hq_db.sql
    ```

- CouchDB
  - Stop Couch:

    ```sh
    ./scripts/docker stop couch
    ```

  - Copy the `couchdb2/` dir to `~/.local/share/dockerhq/couchdb2`.
  - Start Couch

    ```sh
    ./scripts/docker start couch
    ```

  - Fire up Fauxton to check that the dbs are there: http://0.0.0.0:5984/_utils/

- Shared Directory
  - If you are following the default instructions, move/merge the `sharedfiles`
    directory into the HQ root, otherwise do so into the `SHARED_DRIVE_ROOT`
    directory referenced in `localsettings.py`



### Initial Database Population

Before running any of the commands below, you should have all of the following
running: CouchDB, Redis, and Elasticsearch.
The easiest way to do this is using the Docker instructions above.

Populate your database:

```sh
./manage.py sync_couch_views
./manage.py create_kafka_topics
env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
```

You should run `./manage.py migrate` frequently, but only use the environment
variable CCHQ_IS_FRESH_INSTALL during your initial setup.  It is used to skip a
few tricky migrations that aren't necessary for new installs.

#### Troubleshooting

If you have an authentication error running `./manage.py migrate` the first
time, open `pg_hba.conf` (`/etc/postgresql/9.1/main/pg_hba.conf` on Ubuntu)
and change the line "local all all peer" to "local all all md5".

If you have trouble with your first run of `./manage.py sync_couch_views`:

- 401 error related to nonexistent database:

    ```sh
    curl -X PUT http://localhost:5984/commcarehq  # create the database
    curl -X PUT http://localhost:5984/_config/admins/commcarehq -d '"commcarehq"' .  # add admin user
    ```

- Error stemming from any Python modules: the issue may be that your virtualenv
  is relying on the `site-packages` directory of your local Python installation
  for some of its requirements. (Creating your virtualenv with the
  `--no-site-packages` flag should prevent this, but it seems that it does not
  always work). You can check if this is the case by running `pip show
  {name-of-module-that-is-erroring}`. This will show the location that your
  virtualenv is pulling that module from; if the location is somewhere other
  than the path to your virtualenv, then something is wrong. The easiest
  solution to this is to remove any conflicting modules from the location that
  your virtualenv is pulling them from (as long as you use virtualenvs for all
  of your Python projects, this won't cause you any issues).

- If you encounter an error stemming from an Incompatible Library Version of
  libxml2.2.dylib on Mac OS X, try running the following commands:

    ```sh
    brew link libxml2 --force
    brew link libxslt --force
    ```

- If you encounter an authorization error related to CouchDB, try going to your
  `localsettings.py` file and change `COUCH_PASSWORD` to an empty string.


### ElasticSearch Setup

To set up elasticsearch indexes run the following:

```sh
./manage.py ptop_preindex
```

This will create all of the elasticsearch indexes (that don't already exist) and
populate them with any data that's in the database.

Next, set the aliases of the elastic indices. These can be set by a management
command that sets the stored index names to the aliases.

```sh
./manage.py ptop_es_manage --flip_all_aliases
```

### JavaScript

#### Installing Yarn

We use Yarn to manage our JavaScript dependencies. It is able to install older
`bower` dependencies/repositories that we still need and `npm` repositories.
Eventually we will move fully to `npm`, but for now you will need `yarn` to
manage `js` repositories.

In order to download the required JavaScript packages, you'll need to install
`yarn` and run `yarn install`. Follow these steps to install:

1. Follow [these steps](https://classic.yarnpkg.com/en/docs/install#mac-stable)
   to install Yarn.

2. Install dependencies with:

    ```sh
    yarn install --frozen-lockfile
    ```

NOTE: if you are making changes to `package.json`, please run `yarn install`
without the `--frozen-lockfile` flag so that `yarn.lock` will get updated.


##### Troubleshooting Javascript dependency installation

Depending on your operating system, and what version of `nodejs` and `npm` you
have locally, you might run into issues. Here are minimum version requirements
for these packages.

```sh
$ npm --version
6.14.4
$ node --version
v12.18.1
```

On a clean Ubuntu 18.04 LTS install, the packaged nodejs version is v8. The
easiest way to get onto the current nodejs v12 is

```sh
curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash -
sudo apt install -y nodejs
```

#### Using LESS (2 Options)

##### Option 1: Let Client Side Javascript (less.js) handle it for you

This is the setup most developers use. If you don't know which option to use,
use this one. It's the simplest to set up and the least painful way to develop:
just make sure your `localsettings.py` does not contain `COMPRESS_ENABLED` or
`COMPRESS_OFFLINE` settings (or has them both set to `False`).

The disadvantage is that this is a different setup than production, where LESS
files are compressed.

##### Option 2: Compress OFFLINE, just like production

This mirrors production's setup, but it's really only useful if you're trying to
debug issues that mirror production that's related to staticfiles and
compressor. For all practical uses, please use Option 1 to save yourself the
headache.

Make sure your `localsettings.py` file has the following set:

```python
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

For all STATICFILES changes (primarily LESS and JavaScript), run:

```sh
./manage.py collectstatic
./manage.py compilejsi18n
./manage.py fix_less_imports_collectstatic
./manage.py compress
```


### Formplayer

Formplayer is a Java service that allows us to use applications on the web
instead of on a mobile device.

In `localsettings.py`:

```python
FORMPLAYER_URL = 'http://localhost:8080'
LOCAL_APPS += ('django_extensions',)
```

When running HQ, be sure to use `runserver_plus`:

```sh
./manage.py runserver_plus 0.0.0.0:8000
```

Then you need to have Formplayer running.


#### Prerequisites

Before running Formplayer, you need to [initialize the formplayer database](https://github.com/dimagi/formplayer#building-and-running).
The password for the "commcarehq" user is in the localsettings.py file in the
`DATABASES` dictionary.

```sh
createdb formplayer -U commcarehq -h localhost
```

The fastest way to get Formplayer running outside of docker is to download the
`application.properties` and `formplayer.jar` files and run it directly. You may
download and run these in the commcare-hq repo root (these files are excluded
from git in the `.gitignore` file).

```sh
curl https://raw.githubusercontent.com/dimagi/formplayer/master/config/application.example.properties -o application.properties
curl https://s3.amazonaws.com/dimagi-formplayer-jars/latest-successful/formplayer.jar -o formplayer.jar
```

Thereafter, to run Formplayer, navigate to the dir where you installed them
above (probably the repo root), and run:

```sh
java -jar ./formplayer.jar
```

This starts a process in the foreground, so you'll need to keep it open as long
as you plan on using Formplayer.

To keep Formplayer up to date with the version used in production, you can add
the `curl` commands above to your `hammer` command (see [hammer.sh](scripts/hammer.sh)),
or whatever script you use for updating your dev environment.


### Browser Settings

We recommend disabling the cache. In Chrome, go to **Dev Tools > Settings >
Preferences > Network** and check the following:

- [x] Disable cache (while DevTools is open)


## Running CommCare HQ

Make sure the required services are running (PostgreSQL, Redis, CouchDB, Kafka,
Elasticsearch).

```sh
./manage.py check_services
```

Some of the services listed there aren't necessary for very basic operation, but
it can give you a good idea of what's broken.

Then run the following separately:

```sh
# run the Django server
./manage.py runserver 0.0.0.0:8000

# Keeps elasticsearch index in sync
# You can also skip this and run `./manage.py ptop_reindexer_v2` to manually sync ES indices when needed.
./manage.py run_ptop --all --processor-chunk-size=1

# You can also run individual pillows with the following.
# Pillow names can be found in settings.py
./manage.py run_ptop --pillow-name=CaseSearchToElasticsearchPillow --processor-chunk-size=1

# Setting up the asynchronous task scheduler (only required if you have CELERY_TASK_ALWAYS_EAGER=False in settings)
celery -A corehq worker -l info
```

For celery, you may need to add a `-Q` argument based on the queue you want to
listen to.

For example, to use case importer with celery locally you need to run:

```sh
celery -A corehq worker -l info -Q case_import_queue
```

Create a superuser for your local environment

```sh
./manage.py make_superuser <email>
```


## Running Formdesigner (Vellum) in Development mode

By default, HQ uses Vellum minified build files to render form-designer. To use
files from Vellum directly, do the following.

- Make Django expect the Vellum source code in the `submodules/formdesigner`
  directory instead of using a minified build by enabling Vellum "dev mode" in
  `localsettings.py`:

    ```python
    VELLUM_DEBUG = "dev"
    ```

- Clone (or symlink to repo elsewhere on disk) the Vellum repostory into/at the
   `submodules/formdesigner` directory under the commcare-hq repo root:

    ```sh
    # clone directly:
    git clone git@github.com:dimagi/Vellum.git ./submodules/formdesigner

    # -- OR --

    # symlink existing Vellum code at submodules/formdesigner
    ln -s absolute/path/to/Vellum ./submodules/formdesigner
    ```


## Airflow

It is usually not required to have a local airflow environment running.

However, if you do need to get setup on Airflow (which is used to back some
reporting infrastructure) you can follow the instructions in the
[pipes repository](https://github.com/dimagi/pipes/).


## Running Tests

To run the standard tests for CommCare HQ, run

```sh
./manage.py test
```

These may not all pass in a local environment. It's often more practical, and
faster, to just run tests for the django app where you're working.

To run a particular test or subset of tests:

```sh
./manage.py test <test.module.path>[:<TestClass>[.<test_name>]]

# examples
./manage.py test corehq.apps.app_manager
./manage.py test corehq.apps.app_manager.tests.test_suite:SuiteTest
./manage.py test corehq.apps.app_manager.tests.test_suite:SuiteTest.test_picture_format

# alternate: file system path
./manage.py test corehq/apps/app_manager
./manage.py test corehq/apps/app_manager/tests/test_suite.py:SuiteTest
./manage.py test corehq/apps/app_manager/tests/test_suite.py:SuiteTest.test_picture_format
```

To use the `pdb` debugger in tests, include the `s` flag:

```sh
./manage.py test -s <test.module.path>[:<TestClass>[.<test_name>]]
```

If database tests are failing because of a `permission denied` error, give your
Postgres user permissions to create a database.
In the Postgres shell, run the following as a superuser:

```sql
ALTER USER commcarehq CREATEDB;
```


### REUSE DB

To avoid having to run the database setup for each test run you can specify the
`REUSE_DB` environment variable which will use an existing test database if one
exists:

```sh
REUSE_DB=1 ./manage.py test corehq.apps.app_manager
```

Or, to drop the current test DB and create a fresh one

```sh
./manage.py test corehq.apps.app_manager --reusedb=reset
```

See `corehq.tests.nose.HqdbContext` ([source](corehq/tests/nose.py)) for full
description of `REUSE_DB` and `--reusedb`.


### Accessing the test shell and database

The `CCHQ_TESTING` environment variable allows you to run management commands in
the context of your test environment rather than your dev environment.
This is most useful for shell or direct database access:

```sh
CCHQ_TESTING=1 ./manage.py dbshell

CCHQ_TESTING=1 ./manage.py shell
```

### Running tests by tag

You can run all tests with a certain tag as follows:

```sh
./manage.py test --attr=tag
```

Available tags:

- all_backends: all tests decorated with `run_with_all_backeds`

See http://nose.readthedocs.io/en/latest/plugins/attrib.html for more details.


### Running only failed tests

See https://github.com/nose-devs/nose/blob/master/nose/plugins/testid.py


## Javascript tests

### Setup

Make sure javascript packages are installed with the following. Please see the
section on installing `yarn` above for more details.

It's recommended to install grunt globally (with `yarn`) in order to use grunt
from the command line:

```sh
yarn global add grunt
yarn global add grunt-cli
```

You'll then need to add the yarn bin folder to your path:

```sh
export PATH="$(yarn global bin):$PATH"
```

More information can be found [here](https://classic.yarnpkg.com/en/docs/cli/global/)

In order for the tests to run the **development server needs to be running on port 8000**.


### Running tests from the command line

To run all JavaScript tests in all the apps:

```sh
grunt test
```

To run the JavaScript tests for a particular app run:

```sh
grunt test:<app_name>  # (e.g. grunt test:app_manager)
```

To list all the apps available to run:

```sh
grunt list
```


### Running tests from the browser

To run tests from the browser (useful for debugging) visit this url:

```
http://localhost:8000/mocha/<app_name>
```

Occasionally you will see an app specified with a `#`, like `app_manager#b3`.
The string after `#` specifies that the test uses an alternate configuration. To
visit this suite in the browser go to:

```
http://localhost:8000/mocha/<app_name>/<config>
```

For example:
```
http://localhost:8000/mocha/app_manager/b3
```

## Sniffer

You can also use sniffer to auto run the Python tests.

When running, sniffer auto-runs the specified tests whenever you save a file.

For example, you are working on the `retire` method of `CommCareUser`. You are
writing a `RetireUserTestCase`, which you want to run every time you make a
small change to the `retire` method, or to the `testCase`. Sniffer to the
rescue!


### Sniffer Usage

```sh
sniffer -x <test.module.path>[:<TestClass>[.<test_name>]]
```

In our example, we would run

```sh
sniffer -x corehq.apps.users.tests.retire:RetireUserTestCase`
```

You can also add the regular `nose` environment variables, like:

```sh
REUSE_DB=1 sniffer -x <test>
```

For JavaScript tests, you can add `--js-` before the JavaScript app test name,
for example:

```sh
sniffer -x --js-app_manager
```

You can combine the two to run the JavaScript tests when saving js files, and
run the Python tests when saving py files as follows:

```sh
sniffer -x --js-app_manager -x corehq.apps.app_manager:AppManagerViewTest
```

### Sniffer Installation instructions

<https://github.com/jeffh/sniffer/> (recommended to install `pywatchman` or
`macfsevents` for this to actually be worthwhile otherwise it takes a long time
to see the change).
