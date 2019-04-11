Couch model migration
=====================

1. Introduce a postgres django model that saves documents to both couch and postgres
   Example: https://github.com/dimagi/commcare-hq/commit/f6200ea8066a47d1012c9a615124444c32368bd3#diff-1991662efa2c53e4fc57cabf6ba71084R83
2. Save all existing couch docs of that type to postgres
   Example: https://github.com/dimagi/commcare-hq/commit/1c6a3afaa706efb87dbcc8aa56733e43e61894c7#diff-bc810426d81db17be4b0b610cd7a59b2R15
   For large migrations: https://commcare-hq.readthedocs.io/migration_command_pattern.html#auto-managed-migration-pattern
3. Changing all query code so that it pulls data from postgres
   Example: https://github.com/dimagi/commcare-hq/commit/1c6a3afaa706efb87dbcc8aa56733e43e61894c7#diff-1991662efa2c53e4fc57cabf6ba71084R56
4. Removing the couch views
5. Stop saving to couch

Current progress
================

Document | Owner | Phase Completed
---------|-------|----------------
Toggle | @emord | 3

Currently Undocumented/Unexplored
===============================

* Some models such as Application and CommCareUser often pull the JSON without wrapping the JSONObject.
  That's currently not supported by DocumentField
* By default Django cannot create the most useful jsonb indexes.
  This can be done now with a custom index migration.
  Should also be possible in Django 2.2 https://docs.djangoproject.com/en/2.2/ref/models/indexes/#opclasses
* Some models may lend well to partitioning such as Repeaters. Will architect be able to work with this?
