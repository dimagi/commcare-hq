CommCare HQ docker
==================

Initial setup
-------------
* Install [Docker](http://docs.docker.com/installation)
* Install [Docker Compose](https://docs.docker.com/compose/install/)
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

* Configure your localsettings
    
    **NOTE** this is only necessary if you want to run CommCare HQ inside the docker container. If you just want
    to use the services skip this step.

    Make your `localsettings.py` extend `dockersettings.py` and comment out / delete your current
    settings for PostgreSQL, Redis, CouchDB, Elasticsearch
    
    ```python
    from docker.dockersettings import *
    # DATABASES ..
    ```
    
    See `docker/localsettings_docker.py` for an example.

    
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

* Easticsearch (9200 & 9300)
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
  
  $ .travis/simulate.sh python-catchall --test-override app_manager.SuiteTest
  runs only the app_manager.SuiteTest using the python-catchall matrix setup
  
  $ .travis/simulate.sh python-catchall --command-override bash
  drops you into a bash shell in the python-catchall matrix setup from where you can
  run any other commands
  
```

