CommCare HQ docker
==================

The purpose of this docker initiative is to allow non-tech users to install and run offline demo instances of CommCareHQ for training / remote app building. The possibility to mount a source tree into a well-defined container may also help development.

This project is made of :

* a Dockerfile in the root directory that build a docker image containing the latest version of CommCareHQ
* scripts in the docker folder to build / instanciate / start / stop a CommCareHQ stack


Try it
------

* [install docker](http://docs.docker.com/installation)
* run {commcare-hq}/docker/docker-run.sh
* connect to http://[hostip]:8000
* login: example@example.com / password: example
* [install commcare-mobile builds](https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/builds)


Notes
-----

* It is possible to mount a git clone into a commcare-hq container with the -v option : `docker run --link postgres:postgres --link couchdb:couchdb --link redis:redis --link elasticsearch:elasticsearch -p 8000:8000 -v /path/to/clone:/usr/src/commcare-hq -i -t charlesfleche/commcare-hq /bin/bash`. /usr/src/commcare-hq is the default source location within the image.
* BASE_ADDRESS can be set with the environment variable BASE_HOST, with a fall back to localhost. In the docker-run.sh BASE_HOST is set by taking the first address returned by `hostname -I`. This is not ideal…
* Each commit to [my docker branch](https://github.com/charlesfleche/commcare-hq/tree/docker) triggers a [charlesfleche/commcare-hq](https://registry.hub.docker.com/u/charlesfleche/commcare-hq/) image build.
* I am not using [fig](http://www.fig.sh/) for the time being as the current goal is to target deployments on OSX / Windows laptops.
* Wheezy has been choosen as a base image because the official redis, postgres and couchdb are based on the same image, potentialy reducing the amount of data to download.
* Databases initializations (users, db, django) is done by instanciating temporary couchdb / postgres / commcarehq images that already contain the necessary binaries (like psql).
* Celery, rabbitmq and other components not strictly necessary for a laptop install are not part of this setup.


Caveats
-------

* CloudCare is not currently part of this set up. It should probably be another docker image, different from CommCareHQ.
* Some CommCareHQ pages trigger errors, probably because of missing components / misconfigurations.


Docker Compose
==============

Initial setup
-------------
* Install [Docker](http://docs.docker.com/installation)
* Install [Docker Compose](https://docs.docker.com/compose/install/)
* If you want to run the containers in a VM install [Docker Machine](https://docs.docker.com/machine/install-machine/)
* Make your `localsettings.py` extend `dockersettings.py` and comment out / delete your current
settings for PostgreSQL, Redis, CouchDB, Elasticsearch

```python
from docker.dockersettings import *
# DATABASES ..
```

See `docker/localsettings-docker.py` for an example.

* Bootstrap the setup:

```
  $ ./docker/bootstrap.sh
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

If all goes according to plan you should be able to log into CommCare: http://localhost:8000

    
General usage
-------------
The following commands assumes that you have updated your localsettings as described above.

**Strat/stop the services (couch, postgres, elastic, redis)**

```
  $ ./docker/docker-services.sh start
  $ ./docker/docker-services.sh stop
  
  # For more usages
  $ ./docker/docker-services.sh --help 
```

**Run the django server**

```
  $ sudo docker-compose up
  $ sudo docker-compose up -d  # run in background
```

**Check logs**

```
  $ sudo docker-compose logs web  # assuming you're running the Django server in the background
  $ sudo ./docker/docker-services.sh logs [postgres|elasticsearch|redis|couch]
```

**Start fresh**

```
  $ ./docker/docker-services.sh down
  $ ./docker/docker-services.sh start
  $ sudo docker-compose down
  $ sudo docker-compose up
```

Notes
-----
**rebuild**
After changing any of the python requirements the `web` image will need to be rebuilt:

```
  $ sudo docker-compose build web
```
