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

    Make your `localsettings.py` extend `dockersettings.py` and comment out / delete your current
    settings for PostgreSQL, Redis, CouchDB, Elasticsearch
    
    ```python
    from docker.dockersettings import *
    # DATABASES ..
    ```
    
    See `docker/localsettings_docker.py` for an example.

    
General usage
-------------
The following commands assumes that you have updated your localsettings as described above.

**Print the help**

```
  $ ./dockerhq.sh --help
```

**Start/stop the services (couch, postgres, elastic, redis)**
```
  $ ./dockerhq.sh services start
```

**Run the django server**

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

