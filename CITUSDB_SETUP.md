# Setting up CitusDB for use in CommCare

[CitusDB](https://docs.citusdata.com/) is a distributed SQL database built on top of PostgreSQL.

## CitusDB in Travis tests
1. Citus containers added directly to the hq-compose.yml file
   to make the setup simpler rather than having separate compose files
   and having to join the networks or use host networking
2. Since there is only a single DB in the Citus cluster (the `postgres` database
   does not exist) Django is unable to setup or tear down the database. To get
   around this we use `REUSE_DB=True` which skips database setup and teardown
   for existing databases. Other databases that do not exist will be setup, but
   teardown will be skipped.

   Having Django setup the test database requires doing it in Django migrations.
   Although this works it adds a lot of time to the test setup since Django
   needs to run migrations on the worker nodes. To keep the setup time lower we
   skip it.

## Running CitusDB
To run CitusDB in docker execute the following command:
```
$ ./scripts/docker citus up -d
```

This will spin up 3 containers:

* citus_master (port 5600)
* citus_worker1 (port 5601)
* citus_worker2 (port 5602)

By default the `postgres` database will be configured on all nodes
with the citus extension and with the worker nodes added to the
master node.

For info on how that works see the [Citus docs](http://docs.citusdata.com/en/stable/installation/single_machine_docker.html)

## Django settings
The following database settings should be added to `localsettings.py`:
```python
DATABASES.update({
    'icds-ucr': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'NAME': 'commcare_ucr_citus',
        'USER': 'commcarehq',
        'PASSWORD': 'commcarehq',
        'HOST': 'localhost',
        'PORT': '5600',
        'TEST': {
            'SERIALIZE': False,
            # this ensures the master gets created after / destroyed before the workers
            'DEPENDENCIES': ['citus-ucr-worker1', 'citus-ucr-worker2'],
        },
        'ROLE': 'citus_master'
    },
    'citus-ucr-worker1': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'NAME': 'commcare_ucr_citus',
        'USER': 'commcarehq',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5601',
        'TEST': {
            'SERIALIZE': False,
        },
        'ROLE': 'citus_worker',
        'CITUS_NODE_NAME': 'citus_worker1:5432'
    },
    'citus-ucr-worker2': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'NAME': 'commcare_ucr_citus',
        'USER': 'commcarehq',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '5602',
        'TEST': {
            'SERIALIZE': False,
        },
        'ROLE': 'citus_worker',
        'CITUS_NODE_NAME': 'citus_worker2:5432'
    },
})
```

And for ICDS dashboard development add the following:

```python
ICDS_USE_CITUS = True

REPORTING_DATABASES.update({
    'icds-ucr-citus': 'icds-ucr',
})
```

**ROLE**

This setting allows Django to know which DB is the master
and which are workers. This allows it to run migrations
during test setup which will add the citus extension
and add the worker nodes to the master.

This ROLE is not set for Travis so that we can skip the expensive test setup.

**CITUS_NODE_NAME**

By default when Django creates the test database on the master
node it will add the worker nodes using the `HOST` and `PORT`.
In some cases this doesn't work e.g. if you
are running Django outside of Docker. In this case the
master node will not be able to access the worker nodes
with the same hostname that Django uses. Setting `CITUS_NODE_NAME`
will override the host and port for master to worker communications.

## Setting up the database

There are two ways to do the database setup. In both cases you will need
to manually create the databases:

```
$ psql -h localhost -p 5600 -U commcarehq -c 'create database commcare_ucr_citus;' postgres
$ psql -h localhost -p 5601 -U commcarehq -c 'create database commcare_ucr_citus;' postgres
$ psql -h localhost -p 5602 -U commcarehq -c 'create database commcare_ucr_citus;' postgres
```

Now we can configure the databases in either of the following ways:

1. Django migrations

    Django will automatically setup test databases however it will
    not run the necessary migrations outside of the test setup.
    In order to have Django do the setup for you add the following
    to your `locasettings.py` file:

    ```python
    LOCAL_APPS = LOCAL_APPS + (
        'testapps.citus_master',
        'testapps.citus_worker',
    )
    DATABASE_ROUTERS = ['testapps.citus_master.citus_router.CitusDBRouter']
    ```

    Run Django migrate:
    ```
    $ ./manage.py migrate_multi
    ```

2. Manual setup

    **master node**

    Connect to your database on the master node:
    ```
    $ psql -h localhost -p 5600 -U commcarehq commcare_ucr_citus
    ```
    ```sql
    CREATE EXTENSION citus;
    SELECT * from master_add_node('citus_worker1', 5432);
    SELECT * from master_add_node('citus_worker2', 5432);

    ```

    **worker nodes**

    Connect to your database on each worker node:

    ```
    $ psql -h localhost -p 560[1,2] -U commcarehq commcare_ucr_citus
    ```
    ```sql
    CREATE EXTENSION citus;
    ```

## Troubleshooting

### Deadlock error on `migrate_multi`

If you get deadlock errors running `migrate_multi` during initial setup, one workaround that has resolved this
for at least two developers is to drop and recreate the databases.
**This is a destructive operation so make sure you don't mind losing all your local data.**

To drop the databases you may need to also kill all active sessions.

First get a shell:

```bash
psql -h localhost -p 560[0,1,2] -U commcarehq postgres
```

And run:

```sql
-- drop active connections
SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'commcare_ucr_citus'  AND pid <> pg_backend_pid();
-- drop db
DROP DATABASE commcare_ucr_citus;
-- recreate db
CREATE DATABASE commcare_ucr_citus;
```

Note that you'll have to repeat this process on all three DBs.
