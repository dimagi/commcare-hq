# Setting up CommCare HQ for Developers

This document describes setting up a development environment for working on
CommCare HQ. Such an environment is not suitable for real projects. Production
environments should be deployed and managed [using
commcare-cloud](https://dimagi.github.io/commcare-cloud/).

These instructions are for Mac or Linux computers. For Windows, consider using
an Ubuntu virtual machine.

Once your environment is up and running, bookmark the [dev FAQ](https://github.com/dimagi/commcare-hq/blob/master/DEV_FAQ.md)
for common issues encountered in day-to-day HQ development.

## (Optional) Copying data from an existing HQ install

If you're setting up HQ on a new computer, you may have an old, functional
environment around.  If you don't want to start from scratch, back up your
Postgres and Couch data.

- PostgreSQL
  - Create a pg dump.  You'll need to verify the host IP address:

    ```sh
    pg_dump -h localhost -U commcarehq commcarehq > /path/to/backup_hq_db.sql
    ```

- CouchDB
  - From a non-Docker install: Copy `/var/lib/couchdb2/`.
  - From a Docker install: Copy `~/.local/share/dockerhq/couchdb2`.

- Shared Directory
  - If you are following the default instructions, copy the `sharedfiles`
    directory from the HQ root folder, otherwise copy the directory referenced
    by `SHARED_DRIVE_ROOT` in `localsettings.py`

Save those backups to somewhere you'll be able to access from the new environment.



## Prerequisites

NOTE: Developers on Mac OS have additional prerequisites. See the [Supplementary Guide for Developers on Mac OS](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md).

- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

    ```sh
    sudo apt install git
    ```

- [Python 3.9](https://www.python.org/downloads/)

  - **Linux**:

    In Ubuntu you will also need to install the modules for `python-dev`, `pip`, and `venv` explicitly.

    The [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa)
    allows you to use multiple versions of Python on your own machine as we do
    in production environments. The deadsnakes PPA supports Ubuntu LTS
    releases, but you can use their Python versions on interim Ubuntu releases
    as follows:

    1. Find the name of your Ubuntu release if you don't already know it:
       ```shell
       $ cat /etc/lsb-release
       DISTRIB_ID=Ubuntu
       DISTRIB_RELEASE=23.04
       DISTRIB_CODENAME=lunar  # <-- This is the name you want
       DISTRIB_DESCRIPTION="Ubuntu 23.04"
       ```

    2. Pin your release's package priority to 1001 so that deadsnakes packages
       can't replace official packages, even if they are newer:
       ```shell
       $ cat << EOF | sudo tee /etc/apt/preferences.d/99lunar
       Package: *
       Pin: release lunar
       Pin-Priority: 1001
       EOF
       ```
       but change "lunar" to the name of the release you are using.

    3. Add the deadsnakes PPA, and install the Python version that CommCare HQ
       requires:
       ```shell
       $ sudo add-apt-repository ppa:deadsnakes/ppa
       ```
       This will create a file in `/etc/apt/sources.list.d/` with the name of your
       release. Change the filename, and the name inside the file, to the latest
       LTS release instead (e.g. "jammy").

    4. Install the version of Python that CommCare HQ requires.
       ```shell
       $ sudo apt update
       $ sudo apt install python3.9 python3.9-dev python3-pip python3.9-venv
       ```

  - **Mac**:

    Mac OS 12.x still comes shipped with Python 2.7 (?!), so you need to explicitly use `python3` instead of `python` (unless you use `pyenv`—which we highly recommend!). First install [homebrew](https://brew.sh/)
    

    ```sh
    brew install python@3.9
    ```


- Requirements of Python libraries, if they aren't already installed.  Some of this comes from
  [pyenv's recommendations](https://github.com/pyenv/pyenv/wiki#suggested-build-environment)

  - **Linux**:

    ```sh
    sudo apt-get update; sudo apt install libncurses-dev libxml2-dev libxmlsec1-dev \
    libxmlsec1-openssl libxslt1-dev libpq-dev pkg-config gettext make build-essential \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev
    ```

  - **macOS**:

    ```sh
    brew install libmagic libxmlsec1 libxml2 libxslt openssl readline sqlite3 xz zlib tcl-tk
    ```

- Java (JDK 17)

  - **Linux**:

    install `openjdk-17-jre` via apt:
    ```sh
    sudo apt install openjdk-17-jre
    ```

  - **macOS**:
    See the [Supplementary Guide for Developers on Mac OS](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md)
    as this is quite lengthy.

- PostgreSQL

  Executing postgres commands (e.g. `psql`, `createdb`, `pg_dump`, etc) requires
  installing postgres. These commands are not explicitly necessary, but having
  the ability to run them may be useful.

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

    If you have an M1 chip and are using a Rosetta-based install of Postgres and run into problems with psycopg2, see [this solution](https://github.com/psycopg/psycopg2/issues/1216#issuecomment-767892042).

##### Notes on `xmlsec`

`xmlsec` is a `pip` dependency that will require some non-`pip`-installable
packages. The above notes should have covered these requirements for linux and
macOS, but if you are on a different platform or still experiencing issues,
please see [`xmlsec`'s install notes](https://pypi.org/project/xmlsec/).

If you encounter issues installing `xmlsec` on a M1 mac, you can try following a workaround
outlined in the Mac setup [Supplementary Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md).


## Downloading & Running CommCare HQ

### Step 1: Create your virtual environment and activate it

#### Option A: With `pyenv` and `pyenv-virtualenv`

1. Install `pyenv`

  Full installation instructions are [here](https://github.com/pyenv/pyenv#installation)
  and [here](https://github.com/pyenv/pyenv-installer#installation--update--uninstallation).
  Check [here](https://github.com/pyenv/pyenv/wiki#troubleshooting--faq)
  and [here](https://github.com/pyenv/pyenv/wiki/Common-build-problems) to troubleshoot.

  - **Linux**:

    ```sh
    curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash
    exec $SHELL
    ```

  - **macOS**:

    [see installation guide linked above](https://github.com/pyenv/pyenv#installation)

  - Install python 3.9 with `pyenv`:

    ```sh
    pyenv install 3.9:latest
    ```

    To set Python 3.9 as the global `python`, run:
    ```sh
    pyenv global 3.9.xx  # or whatever version was just installed - it should tab complete
    ```
    Pro-tip: this is great for Mac OS users working around having to explicitly use `python3` :)


2. Create the virtualenv `hq` with Python 3.9.xx:
   ```sh
   pyenv virtualenv 3.9.xx hq
   ```
   Then to enter the environment:
   ```sh
   pyenv activate hq
   ```
   That's it! You may now proceed to Step 2.

#### Option B: With `virtualenvwrapper`

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

#### Option C: With standard Python venv

Virtual environments were introduced as a standard in Python 3.3 [with PEP 405](https://peps.python.org/pep-0405/).

By convention, virtual environments use a ".venv" or "venv" directory in the
root of the codebase. Once you have cloned the CommCare HQ repo in "Step 2"
below, create a Python 3.9 virtual environment in the root of the codebase
with:
```shell
$ python3.9 -m venv .venv
```

For convenience, you can create an alias to activate virtual environments in
".venv" and "venv" directories. To do that, add the following to your
`.bashrc` or `.zshrc` file:
```shell
alias venv='if [[ -d .venv ]] ; then source .venv/bin/activate ; elif [[ -d venv ]] ; then source venv/bin/activate ; fi'
```
Then you can activate virtual environments with
```shell
$ venv
```


### Step 2: Clone this repo and install requirements

1. Once all the dependencies are in order, please do the following:

    ```sh
    git clone https://github.com/dimagi/commcare-hq.git
    cd commcare-hq
    git submodule update --init --recursive
    git-hooks/install.sh
    setvirtualenvproject  # optional, virtualenvwrapper only - sets this directory as the project root
    ```

2. Next, install the appropriate requirements (**only one is necessary**).

    NOTE: If this fails you may need to [install the prerequisite system dependencies](#prerequisites).

    **Mac OS:** Issues? See the [Supplementary Guide for Developers on Mac OS](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md).

  - Recommended for those developing CommCare HQ

    ```sh
    pip install -r requirements/dev-requirements.txt
    ```

    - Recommended for developers or others with custom requirements. Use this `pip
      install ...` workflow for initial setup only. Then create a copy of local.in.sample,
      ```sh
      cp requirements/local.in.sample requirements/local.in
      ```
      and follow the instructions in `local.in` to keep requirements in sync.

    If you have problems installing pip dependencies related to a missing wheel package, try installing wheel and upgrade pip before attempting to install dependencies.

    - If you have ARM64 architecture (Apple M1 chip) and you're having trouble installing ReportLab:
        ```sh
        CFLAGS="-Wno-error=implicit-function-declaration" pip install -r requirements/local.in
        ```
        [Source](https://stackoverflow.com/questions/64871133/reportlab-installation-failed-after-upgrading-to-macos-big-sur)


Note that once you're up and running, you'll want to periodically re-run these
steps, and a few others, to keep your environment up to date. Some developers
have found it helpful to automate these tasks. For pulling code, instead of `git pull`,
you can run [this script](https://github.com/dimagi/commcare-hq/blob/master/scripts/update-code.sh)
to update all code, including submodules. [This script](https://github.com/dimagi/commcare-hq/blob/master/scripts/hammer.sh)
will update all code and do a few more tasks like run migrations and update
libraries, so it's good to run once a month or so, or when you pull code and
then immediately hit an error.

### Step 3: Set up `localsettings.py`

First create your `localsettings.py` file:

```sh
cp localsettings.example.py localsettings.py
```

#### Create the shared directory

If you have not modified `SHARED_DRIVE_ROOT`, then run:

```sh
mkdir sharedfiles
```


### Step 4: Set up Docker services

Once you have completed the above steps, you can use Docker to build and run all
of the service containers. There are detailed instructions for setting up Docker
in the [docker folder](docker/README.md). But the following should cover the
needs of most developers.


1. Install docker packages.

  - **Mac**: see [Install Docker Desktop on Mac](https://docs.docker.com/docker-for-mac/install/)
    for docker installation and setup.
  - **Linux**:

    ```sh
    # install docker
    sudo apt install docker.io

    # ensure docker is running
    systemctl is-active docker || sudo systemctl start docker
    # add your user to the `docker` group
    sudo adduser $USER docker
    # log in as yourself again to activate membership of the "docker" group
    su - $USER

    # re-activate your virtualenv (with your venv tool of choice)
    # (virtualenvwrapper)
    workon hq

    # or (pyenv)
    pyenv activate hq

    # or (virtualenv)
    source $WORKON_HOME/hq/bin/activate
    ```

3. Install `docker compose`
  - **Mac**: comes with Docker Desktop
  - **Linux**:
    ```sh
    sudo apt install docker-compose-plugin
    ```

4. Ensure the elasticsearch config files are world-readable (their containers
   will fail to start otherwise).

    ```sh
    chmod 0644 ./docker/files/elasticsearch*.yml
    ```

5. Bring up the docker containers.

    In either of the following commands, omit the `-d` option to keep the
    containers attached in the foreground.

    ```sh
    ./scripts/docker up -d
    # Optionally, start only specific containers.
    ./scripts/docker up -d postgres couch redis elasticsearch5 zookeeper kafka minio formplayer
    ```

   **Mac OS:** Note that you will encounter many issues at this stage.
   We recommend visiting the Docker section in the [Supplementary Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md).


6. If you are planning on running Formplayer from a binary or source, stop the
   formplayer container to avoid port collisions.

    ```sh
    ./scripts/docker stop formplayer
    ```


### Step 5A: (Optional) Copying data from an existing HQ install

If you previously created backups of another HQ install's data, you can now copy
that to the new install. If not, proceed to Step 5B.

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
    psql -U commcarehq -h localhost commcarehq < /path/to/backup_hq_db.sql
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

  - Fire up Fauxton to check that the dbs are there: http://localhost:5984/_utils/
    - As of CouchDB 3.x, Fauxton is no longer shipped in the container and must
      be installed separately:

      ```sh
      npm install -g fauxton
      fauxton
      ```

      Open http://localhost:8000 in a browser. Run fauxton with ``-p PORT`` to
      use a port other than 8000.

- Shared Directory
  - If you are following the default instructions, move/merge the `sharedfiles`
    directory into the HQ root, otherwise do so into the `SHARED_DRIVE_ROOT`
    directory referenced in `localsettings.py`


### Step 5B: Initial Database Population

Before running any of the commands below, you should have all of the following
running: Postgres, CouchDB, Redis, and Elasticsearch.
The easiest way to do this is using the Docker instructions above.

If you want to use a partitioned database, change
`USE_PARTITIONED_DATABASE = False` to `True` in `localsettings.py`.

You will also need to create the additional databases manually:

```sh
$ psql -h localhost -p 5432 -U commcarehq
```

(assuming that "commcarehq" is the username in `DATABASES` in
`localsettings.py`). When prompted, use the password associated with the
username, of course.

```sh
commcarehq=# CREATE DATABASE commcarehq_proxy;
CREATE DATABASE
commcarehq=# CREATE DATABASE commcarehq_p1;
CREATE DATABASE
commcarehq=# CREATE DATABASE commcarehq_p2;
CREATE DATABASE
commcarehq=# \q
```

Populate your database:

```sh
$ ./manage.py sync_couch_views
$ ./manage.py create_kafka_topics
$ env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate --noinput
```

If you are using a partitioned database, populate the additional
databases too, and configure PL/Proxy:

```sh
$ env CCHQ_IS_FRESH_INSTALL=1 ./manage.py migrate_multi --noinput
$ ./manage.py configure_pl_proxy_cluster --create_only
```

You should run `./manage.py migrate` frequently, but only use the environment
variable CCHQ_IS_FRESH_INSTALL during your initial setup.  It is used to skip a
few tricky migrations that aren't necessary for new installs.

#### Troubleshooting errors from the CouchDB Docker container

If you are seeing errors from the CouchDB Docker container that include
`database_does_not_exist` ... `"_users"`, it could be because CouchDB
is missing its three system databases, `_users`, `_replicator` and
`_global_changes`. The `_global_changes` database is not necessary if
you do not expect to be using the global changes feed. You can use
`curl` to create the databases:

```sh
$ curl -X PUT http://username:password@127.0.0.1:5984/_users
$ curl -X PUT http://username:password@127.0.0.1:5984/_replicator
```

where "username" and "password" are the values of "COUCH_USERNAME"
and "COUCH_PASSWORD" given in `COUCH_DATABASES` set in
`dev_settings.py`.

#### Troubleshooting Issues with `sync_couch_views`

**Mac OS M1 Users:** If you see the following error, check the [Supplementary Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md).
```sh
ImportError: failed to find libmagic.  Check your installation
```

#### Troubleshooting Issues with `migrate`

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

- If you get errors saying "Segmentation fault (core dumped)", with a warning like
  "RuntimeWarning: greenlet.greenlet size changed, may indicate binary incompatibility.
  Expected 144 from C header, got 152 from PyObject" check that your Python version is correct (3.9).
  Alternatively, you can try upgrading `gevent` (`pip install --upgrade gevent`) to fix this error
  on Python 3.8, but you may run into other issues!

### Step 6: Populate Elasticsearch

To set up elasticsearch indexes run the following:

```sh
./manage.py ptop_preindex [--reset]
```

This will create all the elasticsearch indexes (that don't already exist) and
populate them with any data that's in the database.


### Step 7: Installing JavaScript and Front-End Requirements

#### Install Dart Sass

We are transitioning to using `sass`/`scss` for our stylesheets. In order to compile `*.scss`,
Dart Sass is required.

We recommend using `npm` to install this globally with:
```
npm install -g sass
```

You can also [follow the instructions here](https://sass-lang.com/install) if you encounter issues with this method.


#### Installing Yarn

We use Yarn to manage our JavaScript dependencies. It is able to install older
`bower` dependencies/repositories that we still need and `npm` repositories.
Eventually we will move fully to `npm`, but for now you will need `yarn` to
manage `js` repositories.

In order to download the required JavaScript packages, you'll need to install
`yarn` and run `yarn install`. Follow these steps to install:

1. Follow [these steps](https://classic.yarnpkg.com/en/docs/install)
   to install Yarn.

2. Install dependencies with:

    ```sh
    yarn install --frozen-lockfile
    ```

3. Ensure that `django` translations are compiled for javascript (or it will throw a JS error):
   ```sh
   ./manage.py compilejsi18n
   ```

NOTE: if you are making changes to `package.json`, please run `yarn install`
without the `--frozen-lockfile` flag so that `yarn.lock` will get updated.


##### Troubleshooting Javascript dependency installation

Depending on your operating system, and what version of `nodejs` and `npm` you
have locally, you might run into issues. Here are minimum version requirements
for these packages.

```sh
$ npm --version
8.19.3
$ node --version
v16.19.1
```

On a clean Ubuntu 22.04 LTS install, the packaged nodejs version is expected to be v12. The
easiest way to get onto the current nodejs v16 is

```sh
curl -sL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install -y nodejs
```

### Step 8: Configure CSS Precompilers (2 Options)

#### Requirements: Install Dart Sass

At present, we are undergoing a migration from Bootstrap 3 to 5. Bootstrap 3 uses LESS
as its CSS precompiler, and Bootstrap 5 using SASS / SCSS. You will need both installed.

LESS is already taken care of by `package.json` when you run `yarn install`. In order to
compile SASS, we need Dart Sass. There is a `sass` npm package that can be installed globally with
`npm install -g sass`, however this installs the pure javascript version without a binary. For speed in a
development environment, it is recommended to install `sass` with homebrew:

```shell
brew install sass/sass/sass
```

You can also view [alternative installation instructions](https://sass-lang.com/install/) if homebrew doesn't work for you.

#### Option 1: Compile CSS on page-load without compression

This is the setup most developers use. If you don't know which option to use,
use this one. It's the simplest to set up and the least painful way to develop:
just make sure your `localsettings.py` does not contain `COMPRESS_ENABLED` or
`COMPRESS_OFFLINE` settings (or has them both set to `False`).

The disadvantage is that this is a different setup than production, where LESS/SASS
files are compressed.

#### Option 2: Compress OFFLINE, just like production

This mirrors production's setup, but it's really only useful if you're trying to
debug issues that mirror production that's related to staticfiles and
compressor. For all practical uses, please use Option 1 to save yourself the
headache.

Make sure your `localsettings.py` file has the following set:

```python
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

For all STATICFILES changes (primarily LESS, SASS, and JavaScript), run:

```sh
./manage.py collectstatic
./manage.py compilejsi18n
./manage.py fix_less_imports_collectstatic
./manage.py compress
```


### Step 9: Browser Settings

We recommend disabling the cache. In Chrome, go to **Dev Tools > Settings >
Preferences > Network** and check the following:

- [x] Disable cache (while DevTools is open)


### Step 10: Create a superuser

To be able to use CommCare, you'll want to create a superuser, which you can do by running:

```sh
./manage.py make_superuser <email>
```

This can also be used to promote a user created by signing up to a superuser.

Note that promoting a user to superuser status using this command will also give them the
ability to assign other users as superuser in the in-app Superuser Management page.

### Step 11: Running CommCare HQ

Make sure the required services are running (PostgreSQL, Redis, CouchDB, Kafka,
Elasticsearch).

```sh
./manage.py check_services
```

Some of the services listed there aren't necessary for very basic operation, but
it can give you a good idea of what's broken. If you're not running formplayer
in docker, it will of course fail. Don't worry about celery for now.

Then run the django server with the following command:

```sh
./manage.py runserver localhost:8000
```

You should now be able to load CommCare HQ in a browser at [http://localhost:8000](http://localhost:8000).

#### Troubleshooting Javascript Errors

If you can load the page, but either the styling is missing or you get JavaScript console errors trying to create an account,
try running the JavaScript set up steps again. In particular you may need to run:

```sh
yarn install --frozen-lockfile
./manage.py compilejsi18n
./manage.py fix_less_imports_collectstatic
```

## Running Formplayer and submitting data with Web Apps

Formplayer is a Java service that allows us to use applications on the web  instead of on a mobile device.

In `localsettings.py`:

```python
FORMPLAYER_URL = 'http://localhost:8080'
FORMPLAYER_INTERNAL_AUTH_KEY = "secretkey"
LOCAL_APPS += ('django_extensions',)
```

**IMPORTANT:** When running HQ, be sure to use `runserver_plus`

```sh
./manage.py runserver_plus localhost:8000
```

Then you need to have Formplayer running.

### Running `formplayer` Outside of Docker

#### Prerequisites

Before running Formplayer, you need to [initialize the formplayer database](https://github.com/dimagi/formplayer#building-and-running).
The password for the "commcarehq" user is in the localsettings.py file in the
`DATABASES` dictionary.

```sh
createdb formplayer -U commcarehq -h localhost
```

#### Installation

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


## Running CommCare HQ's supporting jobs

The following additional processes are required for certain parts of the application to work.
They can each be run in separate terminals:


### Running Pillowtop

Pillowtop is used to keep elasticsearch indices and configurable reports in sync.

> **Note**
> Typically, you won't need to run these in a dev environment unless you are testing them.
> It is simpler to run the 'reindex' command to update ES with local changes when needed.
> See [Populate Elasticsearch](#step-6--populate-elasticsearch)

**Mac OS:**  `run_ptop` Will likely not work for you.
See the [Supplementary Guide](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP_MAC.md) for help.

It can be run as follows:

```sh
./manage.py run_ptop --all --processor-chunk-size=1
```

You can also run individual pillows with the following command
(Pillow names can be found in `settings.py`):

```sh
./manage.py run_ptop --pillow-name=CaseSearchToElasticsearchPillow --processor-chunk-size=1
```

Alternatively, you can not run pillowtop and instead manually sync ES indices when needed, by calling the `ptop_reindexer_v2` command.
See the command help for details, but it can be used to sync individual indices like this:

```sh
./manage.py ptop_reindexer_v2 user --reset
```

### Running Celery

Celery is used for background jobs and scheduled tasks.
You can avoid running it by setting `CELERY_TASK_ALWAYS_EAGER=False` in your `localsettings.py`,
though some parts of HQ (especially those involving file uploads and exports) require running it.

This can be done using:

```sh
celery -A corehq worker -l info
```

This will run a worker that will listen to default queue which is named celery.

You may need to add a `-Q` argument based on the queue you want to listen to.

For example, to use case importer with celery locally you need to run:

```sh
celery -A corehq worker -l info -Q case_import_queue
```

You can also run multiple queues on a single worker by passing multiple queue names separated by `,`

```sh
celery -A corehq worker -l info -Q case_import_queue,background_queue
```

If you want to run periodic tasks you would need to start `beat` service along with celery by running

```sh
celery -A corehq beat
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

If you are on arm64 architecture using a non-Dimagi Docker Postgres image:

- If you run into a missing "hashlib.control" or "plproxy.control" file while trying to run tests, it is because you are not using the Dimagi Postgres Docker image that includes the pghashlib and plproxy extensions. You will need to change the USE_PARTITIONED_DATABASE variable in your localsettings.py to False so that you won't shard your test database and need the extensions

```
USE_PARTITIONED_DATABASE = False
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


### Deprecation warnings

Deprecation warnings are converted to errors when running tests unless the
warning has been whitelisted (or unless `PYTHONWARNINGS` is set with a value
that does not convert warnings to errors, more below). The warnings whitelist
can be found in `corehq/warnings.py`.

The `CCHQ_STRICT_WARNINGS` environment variable can be used to convert
non-whitelisted deprecation warnings into errors for all management commands
(in addition to when running tests). It is recommended to add this to your bash
profile or wherever you set environment variables for your shell:

```sh
export CCHQ_STRICT_WARNINGS=1
```

If you don't want strict warnings, but do want to ignore (or perform some other
action on) whitelisted warnings you can use the `CCHQ_WHITELISTED_WARNINGS`
environment variable instead. `CCHQ_WHITELISTED_WARNINGS` accepts any of the
[`PYTHONWARNINGS`](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONWARNINGS)
action values (`ignore`, `default`, `error`, etc).

```sh
export CCHQ_WHITELISTED_WARNINGS=ignore
```

`CCHQ_WHITELISTED_WARNINGS=ignore` is implied when `CCHQ_STRICT_WARNINGS=1` is
set.

If `PYTHONWARNINGS` is set it may override the default behavior of converting
warnings to errors. This allows additional local configuration of personal
whitelist entries, for example. Ensure there is an "error" item as the first
entry in the value to preserve the default behavior of converting warnings to
errors. For example:

```sh
export PYTHONWARNINGS='
error,
ignore:Using or importing the ABCs::kombu.utils.functional,
ignore:Using or importing the ABCs::celery.utils.text,
ignore:the imp module is deprecated::celery.utils.imports,
ignore:unclosed:ResourceWarning'
```

Personal whitelist items may also be added in localsettings.py.


### Running tests by tag

You can run all tests with a certain tag as follows:

```sh
./manage.py test --attr=tag
```

Available tags:

- slow: especially slow tests
- sharded: tests that should get run on the sharded test runner
- es_test: Elasticsearch tests

See http://nose.readthedocs.io/en/latest/plugins/attrib.html for more details.


### Running on DB tests or Non-DB tests

```sh
# only run tests that extend TestCase
./manage.py test --db=only

# skip all tests that extend TestCase but run everything else
./manage.py test --db=skip
```

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

### Measuring test coverage

To generate a JavaScript test coverage report, ensure the development server is
active on port 8000 and run:

```sh
./scripts/coverage-js.sh
```

This script goes through the steps to prepare a report for test coverage of
JavaScript files _that are touched by tests_, i.e., apps and files with 0% test
coverage will not be shown. A coverage summary is output to the terminal and a
detailed html report is generated at ``coverage-js/index.html``.


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
