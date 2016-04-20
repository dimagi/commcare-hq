# Sharding postgresql

We use [PL/Proxy](https://plproxy.github.io/) for sharding.

## Dev setup
The following PostgreSQL extensions are required:

* [PL/Proxy](https://plproxy.github.io)
* [pghashlib][pghashlib]

### Installing PL/Proxy

```
  $ sudo apt-get install postgresql-9.X-plproxy
```

### Installing pghashlib

* Download and extract source from [github][pghashlib]
* Build and install:

```
  $ PG_CONFIG=/usr/lib/postgresql/9.X/bin/pg_config make
  $ sudo PG_CONFIG=/usr/lib/postgresql/9.X/bin/pg_config make install
```

[pghashlib]: https://github.com/markokr/pghashlib

## Prod setup

1. Create the databases and update localsettings:

  * Assuming a 5 DB setup with 1024 shards
  * Update environment ansible YAML config as follows:

```
postgresql_dbs:
  - django_alias: default
    name: "{{localsettings.PG_DATABASE_NAME}}"
  - django_alias: proxy
    name: commcarehq_proxy
  - django_alias: p1
    name: commcarehq_p1
    shards: [0, 204]
  - django_alias: p2
    name: commcarehq_p2
    shards: [205, 409]
  - django_alias: p3
    name: commcarehq_p3
    shards: [410, 614]
  - django_alias: p4  
    name: commcarehq_p4  
    shards: [615, 819]  
  - django_alias: p5
    name: commcarehq_p5  
    shards: [820, 1023]
    
localsettings:
  USE_PARTITIONED_DATABASE: True
```

  * Run the `postgresql` ansible tag.
  * Run the `localsettings` ansible tag.

2. Migrate the databases

```
  $ fab [environment] manage:'migrate_multi --noinput'
```

3. Setup the sharding configuration for PL/Proxy

```
  $ fab [environment] manage:configure_pl_proxy_cluster
```
