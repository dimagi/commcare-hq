***************************************
Migrating models from couch to postgres
***************************************

This is a step by step guide to migrating a single model from couch to postgres.

Conceptual Steps
################

1. Add SQL model
2. Wherever the couch document is saved, create or update the corresponding SQL model
3. Migrate all existing couch documents
4. Whenever a couch document is read, read from SQL instead
5. Delete couch model and any related views

Practical Steps
###############

