User Configurable Reports
=========================

Some rough notes for working with user configurable reports.

To rebuild a table just call the `rebuild_indicators` function in `tasks.py`.

The easiest way to create a table configuration is to do it manually in couch or via a python function.
This will hopefully get easier soon.
For inspiration, look at the example configuration files in tests/data/configs/.

Inspecting database tables
--------------------------

The easiest way to inspect the database tables is to us the sql command line utility.
This can be done by runnning `./manage.py dbshell` or using `psql`.
The naming convention for tables is: `configurable_indicators_[domain name]_[table id]`.
In postgres, you can see all tables by typing `\dt` and use sql commands to inspect the appropriate tables.
