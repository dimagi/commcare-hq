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
* Bootstrap the setup:

```
  $ sudo docker-compose build
  $ sudo docker-compose run web bash
```

You are now in the `web` containers shell and can do the rest of the setup
as described in the CommCare HQ Readme section **Set up your django environment**

General usage
-------------
**Run the django server in the background**

```
  $ sudo docker-compose up -d
```

**Check logs**

```
  $ sudo docker-compose logs <web|redis|postgres|elasticsearch|couch>
```

**Start fresh**

```
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

**data location**
By default the data for ES, PG and Couch is stored in `./docker/data`. To change this
you must set an environment variable to point to the new root location:

```
DOCKER_DATA_ROOT=~/.dockerdata/
```

The path must end in a `/`.

If you're running docker with `sudo` you will need to use `sudo -E`.
