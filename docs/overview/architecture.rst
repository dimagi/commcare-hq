CommCare Architecture Overview
==============================

CommCare Backend Services
-------------------------

The majority of the code runs inside the server process. This contains all of the data models and services that
power the CommCare website.

Each module is a collection of one or more Django applications that each contain the relevant data models, url
mappings and view controllers, templates, and Database views necessary to provide that module’s functionality.

Internal Analytics and transformation Engines
---------------------------------------------

The analytics engines are used for offline processing of raw data to generate aggregated values used in reporting
and analytics. There are a suite of components that are used which are roughly diagrammed below. This offline
aggregation and processing is necessary to keep reports running on huge volumes of data fast.

.. image:: ../images/reporting_architecture.png

Change Processors (Pillows)
---------------------------

Change processors (known in the codebase as pillows) are events that trigger when changes are introduced to the
database. CommCare has a suite of tools that listen for new database changes and do additional processing based on
those changes. These include the analytics engines, as well as secondary search indices and custom report
utilities. All change processors run in independent threads in a separate process from the server process, and are
powered by `Apache Kafka <https://kafka.apache.org/>`_.

Task Queue
----------

The task queue is used for asynchronous work and periodic tasks. Processes that require a long time and significant
computational resources to run are put into the task queue for asynchronous processing. These include data exports,
bulk edit operations, and email services. In addition the task queue is used to provide periodic or scheduled
functionality, including SMS reminders, scheduled reports, and data forwarding services. The task queue is powered
by Celery_, an open-source, distributed task queueing framework.

.. _Celery: https://docs.celeryproject.org

Data Storage Layer
------------------

CommCare HQ leverages the following databases for its persistence layer.

PostgreSQL
~~~~~~~~~~

A large portion of our data is stored in the PostgreSQL_ database, including case data, form metadata, and user
account information.

Also stored in a relational database, are tables of domain-specific transactional reporting data. For a particular
reporting need, our User Configurable Reporting framework (UCR) stores a table where each row contains the relevant
indicators as well as any values necessary for filtering.

For larger deployments the PostgreSQL database is sharded. Our primary data is sharded using a library called
PL/Proxy as well as application logic written in the Python.

PostgreSQL is a powerful, open source object-relational database system. It has more than 15 years of active
development and a proven architecture that has earned it a strong reputation for reliability, data integrity, and
correctness.

See :ref:`commcare_postgresql_configuration`

.. _PostgreSQL: https://www.postgresql.org

CouchDB
~~~~~~~

CommCare uses CouchDB_ as the primary data store for some of its data models, including the application builder
metadata and models around multitenancy like domains and user permissions. CouchDB is an open source database
designed to be used in web applications. In legacy systems CouchDB was also used to store  forms, cases, and SMS
records, though these models have moved to PostgreSQL in recent applications.

CouchDB was primarily chosen because it is completely schema-less. All data is stored as JSON documents and views
are written to index into the documents to provide fast map-reduce-style querying.

In addition CommCare leverages the CouchDB changes feed heavily to do asynchronous and post processing of our data.
This is outlined more fully in the “change processors” section above.

.. _CouchDB: https://couchdb.apache.org/

Elasticsearch
~~~~~~~~~~~~~

Elasticsearch_ is a flexible and powerful open source, distributed real-time search and analytics engine for the
cloud. CommCare uses Elasticsearch for several distinct purposes:

Much of CommCare's data is defined by users in the application configuration. In order to provide performant
reporting and querying of user data CommCare makes use of Elasticsearch.

CommCare also serves portions of the REST API from a read-only copy of form and case data that is replicated in
real time to an Elasticsearch service.

This also allows independent scaling of the transactional data services and the reporting services.

.. _Elasticsearch: https://www.elastic.co/

Devops Automation
-----------------

Fabric / Ansible
~~~~~~~~~~~~~~~~

Fabric and Ansible are deployment automation tools which support the efficient management of cloud resources for
operations like deploying new code, rolling out new server hosts, or running maintenance processes like logically
resharding distributed database. CommCare uses these tools as the foundation for our cloud management toolkit,
which allows us to have predictable and consistent maintenance across a large datacenter.

Dimagi's tool suite, `commcare-cloud <Dimagi's tool suite>`_ is also available on Github

Other services
--------------

Nginx (proxy)
~~~~~~~~~~~~~

CommCare’s main entry point for all traffic to CommCare HQ goes through Nginx_. This is installable via the Ubuntu
software installer. SSL termination happens at Nginx. Web traffic once hitting nginx is then routed to our multiple
web-worker processes running Gunicorn (see below). The routing of traffic is determined by the nginx load balancer
that proxy this traffic transparently to the user, and balances the load between the web processes.

.. _Nginx: https://www.nginx.com/

Redis
~~~~~

Redis_ is an open source document store that is used for caching in CommCareHQ. Its primary use is for general
caching of data that otherwise would require a query to the database to speed up the performance of the site. Redis
also is used as a temporary data storage of large binary file storage for caching export files, image dumps, and
other large downloads.

.. _Redis: https://redis.io/

Apache Kafka
~~~~~~~~~~~~

Kafka_ is a distributed streaming platform used for building real-time data pipelines and streaming apps. It is
horizontally scalable, fault-tolerant, fast, and runs in production in thousands of companies. It is used in
CommCare to create asynchronous feeds that power our ETL and reporting pipelines.

.. _Kafka: https://kafka.apache.org/

RabbitMQ
~~~~~~~~

RabbitMQ_ (RMQ) is an open source Advanced Message Queuing Protocol (AMQP) compliant server. CommCare’s long
running, periodic, and computationally expensive backend processes are queued and executed via the AMQP protocol.

A queuing system is vital for running a large data-heavy website in a smooth and predictable manner. Tasks that are
known to take a while ought to be queued in a background process and not force a user and their browser to “wait”
interminably long for an operation to happen. AMQP and the technologies surrounding it make for a clean, reusable
interface to allow developers to create, execute, and retrieve results from these long running tasks.

The python library that utilizes AMQP and RMQ is the Celery_ project, an open source library for asynchronous task
queuing. A task can be written in python code to do a database operation or other report for CommCareHQ. To execute
the task, the website can transmit a job request that is sent to the RabbitMQ queue. Separate worker processes on
other dedicated machines can receive these tasks requests by querying the RabbitMQ server for new task requests.
Once the worker completes the task, it can then notify the frontend of its completion in various ways. Either
sending an email to the user making the request that the job is completed, and providing a link, or utilizing
redis, updating the content of a URL the user is viewing to show that the task is completed.

.. _RabbitMQ: https://www.rabbitmq.com/

Gunicorn
~~~~~~~~

Gunicorn_ is an out-of-the-box multithreaded HTTP server for Python, including good integration with Django. It allows
CommCare to run a number of worker processes on each worker machine with very little additional setup. CommCare is
also using a configuration option that allows each worker process to handle multiple requests at a time using the
popular event-based concurrency library Gevent. On each worker machine, Gunicorn abstracts the concurrency and
exposes our Django application on a single port. After deciding upon a machine through its load balancer, our proxy
is then able to forward traffic to this machine’s port as if forwarding to a naive single-threaded implementation
such as Django’s built-in "runserver".

.. _Gunicorn: https://gunicorn.org/
