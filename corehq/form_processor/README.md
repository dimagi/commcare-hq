Updating SQL Case and Form models
---------------------------------

1. Update python models
2. Run command
  - `python manage.py makemigrations form_processor`
3. Update psycopg2 type adapters
  - `corehq/form_processor/utils/sql.py`
3. Update SQL functions. Most likely these ones but possible others:
  - `save_form_and_related_models.sql`
4. Run commands:
  - `./manage.py makemigrations sql_accessors --empty`
5. Add operations to empty migration to update the changed SQL functions
6. Run `form_processor` tests


Renaming a SQL function
-----------------------

1. Rename the function definition
2. Rename the function references
3. Rename the function template file to match the function name
4. Create a new migration to delete the old function and add the new one
5. Delete any references to the old SQL template file in old migrations (or
replace them with a `noop_migration` operation if it is the only operation in the migration)
6. Do steps 3-5 for the plproxy function as well
