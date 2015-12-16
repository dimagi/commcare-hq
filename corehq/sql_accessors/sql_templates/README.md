## Debugging functions

Your options are:
1. Log from inside the function
  * http://www.postgresql.org/docs/current/static/plpgsql-errors-and-messages.html
2. Use the pgadmin debugger (see below for installation instructions)

### Install pgadmin3 debugger

Install prerequisites:
* libreadline-dev
* postgresql-server-dev-9.X

Then follow instructions here: http://kirk.webfinish.com/?p=277

**Note if you have multiple versions of PG installed**
You need to build the extensions for the correction version of PostgreSQL. To do this
you must supply the *PG_CONFIG* environment variable:

  $ pwd
  /path/to/postgresql-9.4.5/contrib
  $ PG_CONFIG=/usr/lib/postgresql/9.4/bin/pg_config make
  $ cd pldebugger
  $ PG_CONFIG=/usr/lib/postgresql/9.4/bin/pg_config USE_PGXS=1 make
  $ sudo PG_CONFIG=/usr/lib/postgresql/9.4/bin/pg_config USE_PGXS=1 make install
