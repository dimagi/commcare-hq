CommCare HQ docker
==================

Initial setup
-------------
* Linux
   * Install [Docker](https://docs.docker.com/engine/installation/)
   * Install [Docker Compose](https://docs.docker.com/compose/install/) (Note you can also install in a virtualenv with `$ pip install docker-compose`)
* OS X
   * Install [Docker Toolbox](https://docs.docker.com/toolbox/toolbox_install_mac/). Go through the full tutorial, which will create a default machine.
   * To create a new VM manually, run `docker-machine create default --driver=virtualbox` (not necessary if you followed the Docker Toolbox tutorial).
   * If not using the Quick Start terminal, run `eval $(docker-machine env default)` to set up Docker's environment variables.
* If you have any HQ services currently running (couch, postgres, redis, etc.), you should stop them now. 
* Bootstrap the setup:

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
    
    You can create another user and domain with `$ ./manage.py bootstrap DOMAIN EMAIL PASSWORD`
    
    On Mac, run `docker-machine ip` to get the VM's IP address, which replaces `localhost` in the URL.

### Configure your localsettings

There are two different localsettings configurations, depending on whether HQ is running inside a docker container or on your local machine.

  * Running HQ inside a docker container

    Do nothing; `docker/localsettings.py` will be used inside the container.

  * Running docker services only
    * Copy the appropriate postgres/couch/elasticsearch/redis configurations from `docker/localsettings.py` to `localsettings.py`
    * Replace the `HOST` values in the configurations (e.g. `postgres`) with `localhost`


General usage
-------------

```
  $ ./scripts/docker --help
```

**The services (couch, postgres, elastic, redis, zookeeper, kafka)**
```
  $ ./scripts/docker up -d  # start docker services in background
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

Notes
-----
**copying old data**
If you don't want to start fresh, Farid wrote up some notes on copying data from an old dev environment [here](https://gist.github.com/proteusvacuum/a3884ce8b65681ebaf95).

Caveats
-------

* CloudCare is not currently part of this set up. It should probably be another docker image, different from CommCareHQ.
* Celery, rabbitmq and other components not strictly necessary for a laptop install are not part of this setup.


Travis
------
Travis also uses Docker to run the HQ test suite. To simulate the travis build you can use the `.travis/simulate.sh`
script:

```
  $ ./scripts/docker test
  runs python tests

  $ TEST=javascript ./scripts/docker test
  runs the python sharded tests

  $ TEST=python-sharded ./scripts/docker test
  runs the javascript tests (see .travis.yml for more env variable options)
  
  $ ./scripts/docker test corehq/apps/app_manager/tests/test_suite.py:SuiteTest
  runs only the corehq.apps.app_manager.tests.test_suite.SuiteTest
  
  $ ./scripts/docker bash
  drops you into a bash shell in the docker web container from where you can
  run any other commands
  
```

