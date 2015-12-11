# Requirements

The following PostgreSQL extensions are required:

* [pl_proxy](https://plproxy.github.io)
* [pghashlib][pghashlib]

# Installing pl_proxy

  $ sudo apt-get install postgresql-9.X-plproxy

# Installing pghashlib

* Download and extract source from [github][pghashlib]
* Build and install:

  $ PG_CONFIG=/usr/lib/postgresql/9.X/bin/pg_config make
  $ sudo PG_CONFIG=/usr/lib/postgresql/9.X/bin/pg_config make install

[pghashlib]: https://github.com/markokr/pghashlib
