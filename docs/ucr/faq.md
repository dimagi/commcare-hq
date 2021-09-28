UCR FAQ
========

## What is UCR?
UCR stands for 'User Configurable Report'. They are user-generated reports, created within HQ via Reports->Create New Report
______

## My report is complaining: `The database table backing your report does not exist yet. Please wait while the report is populated.` Why?
This problem is probably occurring for you locally. On Staging and Production environments, report tables are generated upon save by an asynchronous Celery task. Even with `CELERY_TASK_ALWAYS_EAGER=True` in _settings.py_, the code currently will not generate these synchronously.  You can manually generate them via the following management command:
```
./manage.py rebuild_tables_by_domain <domain-name> --initiated_by <HQ_user_id>
```
_______