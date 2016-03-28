# Migrating certain doc types to their own db

## Do prepwork to decouple your doc types

**Note**: These instructions are for people *writing* a migration.
If you're interested in running a migration someone else already wrote,
see [Running the doctype migration](#run-the-doctype-migration) below.

Do a full-text search for each doc_type you're migrating across all `map.js` files
```bash
$ grep -r --include=map.js CommCareUser
```
Are each of those views going to work properly after the doctype is migrated to the new database?

Do any work you need to in order make sure that the doc_types in the apps you're migrating are decoupled
from other ones:
- You may need to break apart design documents so that:
  - Any views that need to be in the new db will end up in the new db
  - Any views that need to be in the current db will remain in the current db
- You may need to have certain design documents show up on *both* the current and new dbs
  - If there are functions that referenced these views wanting both,
    you may need to rewrite those functions to check both dbs
- etc.


## Setting up the migration

### Register the new database
This step creates a new database and allows you to start populating it.
The new database will not yet be used by any production code.

Add variables to `settings.py` representing (1) the database you're currently
using for the apps you're migrating, probably set to `None` (== main db), and
(2) the database you _will_ be using.

Add the new db to the list of extra databases in `COUCH_SETTINGS_HELPER`.

```python
# settings.py

NEW_USERS_GROUPS_DB = 'users'  # the database we will be using
USERS_GROUPS_DB = None  # the database to use (will later be changed to NEW_USERS_GROUPS_DB)
...
COUCH_SETTINGS_HELPER = CouchSettingsHelper(
    COUCH_DATABASE,
    COUCHDB_APPS,
    [NEW_USERS_GROUPS_DB],  # list of secondary databases to register
)
```

### Specify which database to read/write docs to
You'll be migrating at module-level granularity, so replace the modules'
entries in `COUCHDB_APPS` with a `('module_name', DB_TO_USE_FOR_MODULE)` tuple.
```python
# settings.py
...
COUCHDB_APPS = [
...
    ('groups', USERS_GROUPS_DB),
    ('users', USERS_GROUPS_DB),
...
]
```
Remember, `USERS_GROUPS_DB` will point to the main db until you flip it to the
new one in a later step.

### Register the migrator instance
In `corehq/doctypemigrations/migrator_instances.py`, add an object representing your migration
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
        'DomainRemovalRecord',
        'OrgRemovalRecord',
    )
)
```
You'll want to be deliberate about assembling the list of doc types, but as a
starting point, you can try:
```python
import inspect
from corehq.apps.app_manager import model
for name, obj in inspect.getmembers(models):
    if inspect.isclass(obj) and issubclass(obj, models.Document):
        print name
```
(do make sure that you're including only doc types defined *in* the app)

### Specify which databases need which views
The migrator instance will take care of syncing documents to the new db, but
you also need to control which views to start indexing in the new db. Enter
`ExtraPreindexPlugin`.  In a module's `AppConfig`, you can register that
module's design docs to additional databases:

```python
from corehq.preindex import ExtraPreindexPlugin
from django.apps import AppConfig
from django.conf import settings

class UsersAppConfig(AppConfig):
    name = 'corehq.apps.users'

    def ready(self):
        ExtraPreindexPlugin.register('users', __file__, settings.NEW_USERS_GROUPS_DB)
```
There, now the module's views will be in both the old database (as per the line
in `COUCHDB_APPS`), and the new database.

We have some views which aren't tied to modules, some of which are meant to
work on roughly all doc types.  Take a look at `corehq/couchapps/__init__.py`
and make sure to register the appropriate views to your new database.  That
module's README should have some more context.

### Deploy migrator
This can be merged whenever, as the new database will not be used until later, when you flip to it.


## Run the doctype migration

All of the following commands should be run in a screen as the cchq user on a production machine. You can do that by running these commands:

```bash
sudo -iu cchq bash
script /dev/null  # to "own the shell" for screen to work
screen
# hit enter to pass screen's opening page.
# If the current release is too old, set up a new release and use that instead
cd /home/cchq/www/production/current
source python_env/bin/activate
```

To see your options run

```bash
$ ./manage.py run_doctype_migration
CommandError: You may run either of the following commands

./manage.py run_doctype_migration <slug> --initial
./manage.py run_doctype_migration <slug> --continuous

with with the following slugs:

user_db_migration

```

The migration we want to run is called `user_db_migration`, as listed in the help message.

To get a general idea of what we're dealing with, run

```bash
$ ./manage.py run_doctype_migration user_db_migration --stats
Source DB: https://commcarehq:****@commcarehq.cloudant.com/commcarehq
Target DB: https://commcarehq:****@commcarehq.cloudant.com/commcarehq__users

           doc_type             Source  Target
AdminUserRole                   0       0
AdminUserRole-Deleted           0       0
CommCareUser                    82031   0
CommCareUser-Deleted            1       0
DeleteGroupRecord               2904    0
DeleteGroupRecord-Deleted       0       0
DomainRemovalRecord             1259    0
DomainRemovalRecord-Deleted     0       0
Group                           20981   0
Group-Deleted                   2885    0
Invitation                      8498    0
Invitation-Deleted              0       0
OrgRemovalRecord                1       0
OrgRemovalRecord-Deleted        0       0
UserRole                        38102   0
UserRole-Deleted                0       0
WebUser                         13151   0
WebUser-Deleted                 0       0
```

You'll see that by default `-Deleted`-suffixed doc_types are also added to the migration.

Staging cannot create new databases, so you'll need to manually create the appropriate database through cloudant's UI.  It'll be something like `staging_commcarehq__users`.

Now you can begin. Run

```bash
$ ./manage.py run_doctype_migration user_db_migration --initial
```

To do the main dump. You may notice that nothing appears in the target db for a long time.
That is because data is first copied from the source db to `./user_db_migration.log`, and then copied from that file
to the target db.

Once this is done you can check `--stats` again for a basic sanity check. Then run

```bash
$ ./manage.py run_doctype_migration user_db_migration --continuous
```

for a continuous topoff based on the couchdb changes feed.
As that's running, you can check `--stats` to monitor whether you're fully caught up.
`--continuous` will also output "All caught up" each time it reaches the end of the changes feed.

If you're running this after the blocking migration has already been added to the code then you can go ahead and re-deploy which will flip the DB. Don't forget to clean up afterward (see below).


## Flipping the db

Once you're confident the two databases are in sync and sync'ing in realtime,
you'll need to make some commits.

### Commit 1: Add a blocking django migration
Add a blocking django migration to keep anyone from deploying before migrating:

```
./manage.py makemigrations --empty doctypemigrations
```

and then edit the generated file:

```diff
  from django.db import models, migrations
+ from corehq.doctypemigrations.djangomigrations import assert_initial_complete
+ from corehq.doctypemigrations.migrator_instances import users_migration

      operations = [
+         migrations.RunPython(assert_initial_complete(users_migration))
      ]
```

### Commit 2: Flip the db
And then actually do the flip; edit `settings.py`:

```diff
  NEW_USERS_GROUPS_DB = 'users'
- USERS_GROUPS_DB = None
+ USERS_GROUPS_DB = NEW_USERS_GROUPS_DB
```

### Commit 3 [maybe]: Use new views
If there are views with different names in the old and new dbs, your flip PR
should also update those names.

### Commit 4 [maybe]: Flip pillowtop and/or elasticsearch
If a doctype you're migrating is read by pillowtop, you'll need to reset the
checkpoint after the merge.  If it's an elasticsearch pillow, you can instead
trigger an index rebuild by updating the index name in the appropriate mapping
file.

### Do it!
PR, and merge it. Then while `--continuous` is still running, deploy it.

Once deploy is complete, kill the `--continuous` command with `^C`.

## Cleanup

### Delete documents from old db
After you're confident in the change and stability of the site,
it's time to delete the old documents still in the source db.

First you should clean up any doc conflicts, as that can get in the way of
deleting stuff.

```bash
$ ./manage.py delete_doc_conflicts
```

Now you can actually delete the documents:

```bash
$ ./manage.py run_doctype_migration user_db_migration --cleanup
```

Keep in mind that this will likely incur some reindexing overhead in the source db.

If you run `$ ./manage.py run_doctype_migration user_db_migration --stats`, you
should see that only the target database has these doc types in it now.
