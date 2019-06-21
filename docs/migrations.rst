Migrating Database Definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are currently three persistent data stores in CommCare that can be migrated.
Each of these have slightly different steps that should be followed.

General
-------
For all ElasticSearch and CouchDB changes, add a "reindex/migration" flag to your PR.
These migrations generally have some gotchas and require more planning for deploy than a postgres migration.

Adding Data
-----------

Postgres
''''''''
Add the column as a nullable column. Creating NOT NULL constraints can lock the table
and take a very long time to complete. If you wish to have the column be NOT NULL, you
should add the column as nullable and migrate data to have a value before adding a
NOT NULL constraint.

ElasticSearch
'''''''''''''
You only need to add ElasticSearch mappings if you want to search by the field you are adding.
There are two ways to do this:

a. Change the mapping's name, add the field, and using ptop_preindex.
b. Add the field, reset the mapping, and using ptop_preindex with an `in-place` flag.

If you change the mapping's name, you should add reindex/migration flag to your PR and coordinate
your PR to run ptop_preindex in a private release directory. Depending on the index and size,
this can take somewhere between minutes and days.

CouchDB
'''''''
You can add fields as needed to couch documents, but take care to handle the previous documents
not having this field defined.

Removing Data
-------------

General
'''''''
Removing columns, fields, SQL functions, or views should always be done in multiple steps.

1. Remove any references to the field/function/view in application code
2. Wait until this code has been deployed to all relevant environments.
3. Remove the column/field/function/view from the database.


It's generally not enough to remove these at the same time because any old processes could
still reference the to be deleted entity.

Couch
'''''
A separate prune_couch_views will need to be run to remove the view from couch

ElasticSearch
'''''''''''''
If you're removing an index, you can use `prune_es_indices` to remove all indices that are
no longer referenced in code.

Querying Data
-------------

Postgres
''''''''
Creating an index can lock the table and cause it to not respond to queries. If the table is
large, an index is going to take a long time. In that case:

1. Create the migration normally using django.
2. On all large environments, create the index concurrently. One way to do this
   is to use `./manage.py run_sql ... <https://github.com/dimagi/commcare-hq/blob/master/corehq/form_processor/management/commands/run_sql.py>`_
   to apply the SQL to the database.
3. Once finished, fake the migration. Avoid this by using
   `CREATE INDEX IF NOT EXISTS ...` in the migration if possible.
4. Merge your PR.

Couch
'''''
Changing views can block our deploys due to the way we sync our couch views. If you're changing
a view, please sync with someone else who understands this process and coordinate with the team
to ensure we can rebuild the view without issue.


Migration Patterns and Best Practices
-------------------------------------

- :ref:`auto-managed-migration-pattern`
