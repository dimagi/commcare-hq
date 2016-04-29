CommCare HQ docker
==================

Initial setup
-------------
* Linux
   * Install [Docker](https://docs.docker.com/engine/installation/)
   * Install [Docker Compose](https://docs.docker.com/compose/install/) (Note you can also install in a virtualenv with `$ pip install docker-compose`)
* OS X
   * Install [Docker Toolbox](https://docs.docker.com/mac/step_one/). Go through the full tutorial, which will create a default machine.
   * To create a new VM manually, run `docker-machine create default --driver=virtualbox` (not necessary if you followed the Docker Toolbox tutorial).
   * If not using the Quick Start terminal, run `eval $(docker-machine env default)` to set up Docker's environment variables.
* If you have any HQ services currently running (couch, postgres, redis, etc.), you should stop them now. 
* Bootstrap the setup:

    ```
      $ ./dockerhq.sh bootstrap
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

    Make your `localsettings.py` extend `dockersettings.py` and comment out / delete your current
    settings for PostgreSQL, Redis, CouchDB, Elasticsearch
    ```python
    from docker.dockersettings import *
    # DATABASES ..
    ```
    See `docker/localsettings_docker.py` for an example.

  * Running docker services only
    * Copy the appropriate postgres/couch/elasticsearch/redis configurations from `dockersettings.py` to `localsettings.py`
    * Replace the `HOST` values in the configurations (e.g. `postgres`) with `localhost`


General usage
-------------

```
  $ ./dockerhq.sh --help
```

**The services (couch, postgres, elastic, redis, zookeeper, kafka)**
```
  $ ./dockerhq.sh services start
  $ ./dockerhq.sh services stop
  $ ./dockerhq.sh services logs postgres
```
The following services are included. Their ports are mapped to the local host so you can connect to them
directly.

* Elasticsearch (9200 & 9300)
* PostgreSQL (5432)
* CouchDB (5984)
* Redis (6397)
* Zookeeper (2181)
* Kafka (9092)

**Run the django server**

Assumes that you have updated your localsettings as described above.

```
  $ ./dockerhq.sh runserver
```

Notes
-----
**rebuild**
After changing any of the python requirements the `web` image will need to be rebuilt:

```
  $ ./dockerhq.sh rebuild
```

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
  $ .travis/simulate.sh -h
  simulate.sh [javascript|python-catchall|python-group-0|python-sharded]
  
  $ .travis/simulate.sh javascript
  runs the javascript build matrix
  
  $ .travis/simulate.sh python-catchall --override-test app_manager.SuiteTest
  runs only the app_manager.SuiteTest using the python-catchall matrix setup
  
  $ .travis/simulate.sh python-catchall --override-command bash
  drops you into a bash shell in the python-catchall matrix setup from where you can
  run any other commands
  
```

