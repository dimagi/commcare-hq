CommCare HQ in Docker
=====================

Initial setup
-------------

Linux
~~~~~

Install `Docker`_. You should `manage Docker as a non-root user`_.

MacOS
~~~~

Install `Docker Desktop`_. It is available for Mac with Intel, and Mac
with Apple silicon.

.. _Docker: https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository
.. _manage Docker as a non-root user: https://docs.docker.com/install/linux/linux-postinstall/#manage-docker-as-a-non-root-user
.. _Docker Compose: https://docs.docker.com/compose/install/
.. _Docker Desktop: https://docs.docker.com/desktop/install/mac-install/


Running only services in Docker
-------------------------------

There are two different localsettings configurations, depending on
whether HQ is running inside a Docker container or on your local
machine. If you are planning on doing local development, it is
recommended to run HQ on your local machine, and use Docker only for
supporting services.

If you want to run the HQ web worker, Celery and Pillowtop in Docker,
see :ref:`running-services-and-hq`.

If you have any HQ services currently running (Couch, Postgres, Redis,
etc.), you should stop them now.

Run ::

    $ scripts/docker up -d postgres couch redis elasticsearch5 zookeeper kafka minio

to build and start those Docker services in the background. (Omit ``-d``
to run them in the foreground.)

Once the services are all up (``./scripts/docker ps`` to check) you can
return to the CommCare HQ DEV_SETUP and `set up your Django environment`_.

.. _set up your Django environment: https://github.com/dimagi/commcare-hq/blob/master/DEV_SETUP.md#set-up-your-django-environment


.. _running-services-and-hq:

Running services and HQ in Docker
---------------------------------

This setup is useful for running a CommCare HQ test environment, for
example, if you want to build an integration with CommCare.

This setup is not recommended for local development, since you'll
typically want more direct access to the Django process.

.. NOTE::
   This setup is also not appropriate for production use because it runs
   a development web server, a development Celery worker, and the
   PostgreSQL database is not optimized for production.

1. Clone commcare-hq, if you have not done so already::

       $ git clone https://github.com/dimagi/commcare-hq.git
       $ cd commcare-hq
       $ git submodule update --init --recursive

2. Build a Docker image using ``Dockerfile_incl``, and tag it
   "commcare_incl"::

       $ docker build -f Dockerfile_incl -t commcarehq_incl .

3. Create and run service and HQ containers::

       $ scripts/docker runserver

   This will do the following:

   1. Build required images
   2. Run all the service containers
   3. Migrate the DB and sync the Couch views
   4. Bootstrap a superuser and domain if a superuser does not already exist:

      * username: admin@example.com
      * password: Passw0rd!
      * domain: demo
   5. Run the Django dev server

You should be able to log into CommCare at http://localhost:8000 using
the login details above.

On Mac, run `docker-machine ip` to get the VM's IP address, which replaces `localhost` in the URL.

You can create another user and domain with `$ ./manage.py make_superuser <email>`


General usage
-------------

::

    $ ./scripts/docker --help

The services
~~~~~~~~~~~~

::

    $ ./scripts/docker start
    $ ./scripts/docker stop
    $ ./scripts/docker logs postgres

The following services are included. Their ports are mapped to localhost
so you can connect to them directly.

* Elasticsearch (9200 & 9300)
* PostgreSQL (5432)
* CouchDB (5984)
* Redis (6397)
* Zookeeper (2181)
* Kafka (9092)
* MinIO (9980)

CommCare HQ and the services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    $ ./scripts/docker runserver


Your Data
---------

Your Docker data gets mounted based on the `DOCKER_DATA_HOME` variable.

By default on *nix systems this will be **~/.local/share/dockerhq/** so
if you need to manually manipulate data in your Docker volumes this is
the place to do it.

.. NOTE::
   You can destabilize your system if you manually edit data in this
   directory, so do so with care!

Travis
------

Travis also uses Docker to run the HQ test suite. To simulate the Travis
build you can use the **scripts/docker** script.

* Run Python tests::

      $ JS_SETUP=yes ./scripts/docker test

* Run the JavaScript tests::

      $ TEST=javascript ./scripts/docker test

* Run the Python sharded tests::

      $ TEST=python-sharded ./scripts/docker test

* Run only ``corehq.apps.app_manager.tests.test_suite.SuiteTest``::

      $ ./scripts/docker test corehq/apps/app_manager/tests/test_suite.py:SuiteTest

* Drop into a bash shell in the Docker web container from where you can
  run any other commands::

      $ ./scripts/docker bash

* Remove all test containers and volumes::

      $ ./scripts/docker hqtest teardown


Environment variables
---------------------

JS_SETUP=[ yes | **no** ]
   Run ``yarn`` installs. (Default: "no")

TEST=[ javascript | **python** | python-sharded | python-sharded-and-javascript ]
   + ``javascript``: Extra setup and config for JS tests. Also only run
     JS tests
   + ``python`` [default]: Run default tests
   + ``python-elasticsearch-v5``: Configure Django for ES5 tests
   + ``python-sharded``: Configure Django for sharded setup and only run
     subset of tests
   + ``python-sharded-and-javascript``: Combines ``python-sharded`` and
     ``javascript``. Also sends static analysis to Datadog if a job is a
     Travis "cron" event.

NOSE_DIVIDED_WE_RUN
   Only runs a subset of tests. See ``.travis.yml`` for exact options.

REUSE_DB
   Same as normal ``REUSE_DB``

DOCKER_HQ_OVERLAY=[ **none** | overlayfs | **aufs** ]
   + ``none``: Mounts the commcare-hq directory read/write in the Docker
     container for direct access. This is the default when running in
     Travis.
   + ``overlayfs``: Mounts the commcare-hq directory read-only in the
     Docker container and uses it as the "lowerdir" in an ``overlayfs``
     mount to insulate the host OS data from being modified by the
     container.
   + ``aufs``: [deprecated] Same behavior as ``overlayfs``, only using
     Docker's ``aufs`` overlay engine instead of ``overlayfs``. This is
     the default when not running in Travis.

DOCKER_HQ_OVERLAYFS_CHMOD=[ yes | **no** ]
   Perform a recursive chmod on the commcare-hq overlay to ensure read
   access for cchq user. (Default: "no")

DOCKER_HQ_OVERLAYFS_METACOPY=[ on | **off** ]
   Set the ``metacopy=on`` mount option for the overlayfs mount
   (performance optimization, has security implications). (Default: "off")

See ``.travis.yml`` for environment variable options used on Travis.


Run containers with Podman instead of Docker
============================================

Podman 4.3 or later can be used to run HQ containers. Unlike docker, podman is
daemonless and runs containers in rootless mode by default. Podman 4.x is
available on recent versions of Ubuntu. Older versions, such as Ubuntu 22.04,
require `a third-party package repository <https://podman.io/docs/installation#debian>`_.


Install Podman
--------------

.. code:: bash

    sudo apt install podman podman-docker
    
    echo 'export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock' >> ~/.bashrc
    echo 'export DOCKER_SOCK=$XDG_RUNTIME_DIR/podman/podman.sock' >> ~/.bashrc

Create a podman wrapper script named `docker` with the following content
somewhere on your ``PATH`` (``~/.local/bin/docker`` may be a good place if it
is on your ``PATH``).

.. code:: bash

    #! /usr/bin/bash
    if [[ "$1" == compose ]]; then
        shift
        /usr/bin/docker-compose "$@"  # v1, installed by podman-docker
    else
        podman "$@"
    fi

Start containers
----------------

::

    ./scripts/docker up -d
