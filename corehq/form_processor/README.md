Updating SQL Case and Form models
---------------------------------

1. Update python models
2. Run command
  - `python manage.py makemigrations form_processor`
3. Update psycopg2 type adapters
  - `corehq/form_processor/utils/sql.py`
3. Update SQL functions. Most likely these ones but possible others:
  - `save_case_and_related_models.sql`
  - `save_form_and_related_models.sql`
4. Run commands:
  - `./manage.py makemigrations sql_accessors --empty`
5. Add operations to empty migration to update the changed SQL functions
6. Run `form_processor` tests
