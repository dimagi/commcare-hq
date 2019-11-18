CommCare HQ docker
==================

Initial setup
-------------
* Linux
   * Install [Docker](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-using-the-repository)
   * You probably also want to [manage Docker as non-root user](https://docs.docker.com/install/linux/linux-postinstall/#manage-docker-as-a-non-root-user)
   * Install [Docker Compose](https://docs.docker.com/compose/install/) (Note you can also install in a virtualenv with `$ pip install docker-compose`)
* OS X
   * Preferred: install [Docker for Mac](https://docs.docker.com/docker-for-mac/install/).
   * Alternate for older Macs that do not support Docker for Mac:
     * Install [Docker Toolbox](https://docs.docker.com/toolbox/toolbox_install_mac/). Go through the full tutorial, which will create a default machine.
     * To create a new VM manually, run `docker-machine create default --driver=virtualbox` (not necessary if you followed the Docker Toolbox tutorial).
     * If not using the Quick Start terminal, run `eval $(docker-machine env default)` to set up Docker's environment variables.

* If you have any HQ services currently running (couch, postgres, redis, etc.), you should stop them now. 

There are two different localsettings configurations, depending on whether HQ is running inside a docker container or on your local machine. If you are planning on doing local development, it is recommended to run HQ on your local machine, and use docker only for supporting services

### Run only services in docker

This is the recommended setup for local development.  If you want to run the server process in docker, see below.

* If you are using _Docker Toolbox_ (not _Docker for Mac_): change all service host settings (DATABASES HOST, COUCH_SERVER_ROOT, etc.) in your localsettings.py file to point to the IP address of your virtualbox docker VM.
* Run `./scripts/docker up -d postgres couch redis elasticsearch kafka minio` to build and start those docker services in the background.
* Once the services are all up (`./scripts/docker ps` to check) you can return to the CommCare HQ DEV_SETUP and [Setup your Django environment](https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#set-up-your-django-environment).

### Run services and HQ in docker

This setup is not recommended for local development, since you'll typically want more direct access to the django process.

Bootstrap the setup.

```
$ ./scripts/docker runserver --bootstrap
```

This will do the following:

* build all the images (if not already built)
* run all the service containers
* migrate the DB and sync the Couch views
* bootstrap a superuser and domain:
  * username: admin@example.com
  * password: password
  * domain: demo
* run the Django dev server

If all goes according to plan you should be able to log into CommCare: http://localhost:8000 using
the login details above.

You can create another user and domain with `$ ./manage.py make_superuser <email>`

On Mac, run `docker-machine ip` to get the VM's IP address, which replaces `localhost` in the URL.


General usage
-------------

```
  $ ./scripts/docker --help
```

**The services (couch, postgres, elastic, redis, zookeeper, kafka)**
```
  $ ./scripts/docker start
  $ ./scripts/docker stop
  $ ./scripts/docker logs postgres
```
The following services are included. Their ports are mapped to the local host so you can connect to them
directly.

* Elasticsearch (9200 & 9300)
* PostgreSQL (5432)
* CouchDB (5984)
* Redis (6397)
* Zookeeper (2181)
* Kafka (9092)
* Riak CS (9980)

**Run the django server**

```
  $ ./scripts/docker runserver
```

Caveats
-------

* CloudCare is not currently part of this set up. It should probably be another docker image, different from CommCareHQ.
* Celery, rabbitmq and other components not strictly necessary for a laptop install are not part of this setup.


Travis
------
Travis also uses Docker to run the HQ test suite. To simulate the travis build you can use the `./scripts/docker`
script:

```
  $ JS_SETUP=yes ./scripts/docker test
  runs python tests

  $ TEST=javascript ./scripts/docker test
  runs the javascript tests

  $ TEST=python-sharded ./scripts/docker test
  runs the python sharded tests
  
  $ ./scripts/docker test corehq/apps/app_manager/tests/test_suite.py:SuiteTest
  runs only the corehq.apps.app_manager.tests.test_suite.SuiteTest
  
  $ ./scripts/docker bash
  drops you into a bash shell in the docker web container from where you can
  run any other commands
  
  $ ./scripts/docker hqtest teardown
  remove all test containers and volumes
  
```

ENV Vars
~~~~~~~~

* JS_SETUP=yes
  * Run `npm` and `bower` installs
* TEST=[javascript|python|python-sharded]
  * javascript: extra setup and config for JS tests. Also only run JS tests
  * python: default tests
  * python-sharded: configure django for sharded setup and only run subset of tests
* NOSE_DIVIDED_WE_RUN
  * used to only run a subset of tests
  * see .travis.yml for exact options
* REUSE_DB
  * Same as normal REUSE_DB
 
See .travis.yml for env variable options used on travis.
