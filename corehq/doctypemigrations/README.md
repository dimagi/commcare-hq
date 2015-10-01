# Migrating certain doc types to their own db

## Do prepwork to decouple your doc types

To `settings.py` add variables representing
(1) the database you're currently using for the apps you're migrating, probably set to `None` (== main db),
and (2) the database you _will_ be using.
to start with:

```python

NEW_USERS_GROUPS_DB = 'users'  # the database we will be using
USERS_GROUPS_DB = None  # the database to use
...
COUCHDB_APPS = [
...
    ('groups', USERS_GROUPS_DB),
    ('users', USERS_GROUPS_DB),
...
]
```

Do any work you need to in order make sure that the doc_types in the apps you're migrating are decoupled
from other ones:
- You may need to break apart design documents so that:
  - Any views that need to be in the new db will end up in the new db
  - Any views that need to be in the current db will remain in the current db
- You may need to have certain design documents show up on *both* the current and new dbs
  - If there are functions that referenced these views wanting both,
    you may need to rewrite those functions to check both dbs
- etc.


## Add your migrator instance

To `corehq/doctypemigrations/migrator_instances.py` your an object representing your migration
going off the following model:

```python
users_migration = Migrator(
    slug='user_db_migration',
    source_db_name=None,
    target_db_name=settings.NEW_USERS_GROUPS_DB,
    doc_types=(
        'Group',
        'DeleteGroupRecord',
        'UserRole',
        'AdminUserRole',
        'CommCareUser',
        'WebUser',
        'Invitation',
        'DomainInvitation',
        'DomainRemovalRecord',
        'OrgRemovalRecord',
    )
)
```
