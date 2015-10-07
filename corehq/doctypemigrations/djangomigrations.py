from django.conf import settings


MIGRATION_MESSAGE = """
Before you can merge you must run the {slug} doc_type migration.

If you're seeing this on your **dev machine**, run

./manage.py sync_couchdb
./manage.py run_doctype_migration {slug} --initial
./manage.py migrate

and that final migrate should go through without a hitch.

After you migrate/update your code and everything's working fine, run

./manage.py run_doctype_migration {slug} --cleanup

to delete the documents from the source db that have been copied to the target db


If you're seeing this on a **production deploy** (or are just curious),
you should read the full instructions here for the zero-downtime live swap:

https://github.com/dimagi/commcare-hq/blob/master/corehq/doctypemigrations/README.md#run-the-doctype-migration.
"""


class MigrationNotComplete(Exception):
    pass


def assert_initial_complete(migrator):
    def forwards(apps, schema_editor):
        if not migrator.last_seq and not settings.UNIT_TESTING:
            raise MigrationNotComplete(MIGRATION_MESSAGE.format(slug=migrator.slug))
    return forwards
