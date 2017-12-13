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


Updating a SQL function
-----------------------

1. Rename the file the function is being declared in e.g. `get_case.sql -> get_case_2.sql`
    1. We do this avoid situations where the migrations aren't added which
    wouldn't fail in tests but would fail in production.
2. Replace all references to the old file in existing migrations with `noop_migration`
    1. Or you can just remove it completely if there are other migration operations
    happening in the migration.
3. Create a migration to drop and re-create the function.
    1. Make sure you include an context variables required in the function

    ```
    # -*- coding: utf-8 -*-
    from __future__ import absolute_import
    from __future__ import unicode_literals
    from django.db import migrations
    from corehq.sql_db.operations import RawSQLMigration
    
    migrator = RawSQLMigration(('corehq', 'sql_accessors', 'sql_templates'), {
        'context_key': 'context_value'
    })
    
    class Migration(migrations.Migration):
    
        dependencies = [
            ('sql_accessors', 'XXXX_migration_name'),
        ]
    
        operations = [
            migrator.get_migration('get_case_2.sql'),
        ]
    ```

4. Make changes to the function as required.

If the function signature is changing:

1. Repeat steps 1-4 above for the pl_proxy function (file in `corehq/sql_proxy_accessors`)
2. Update callers of the function in code.
