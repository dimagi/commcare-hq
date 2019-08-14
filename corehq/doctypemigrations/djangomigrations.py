from __future__ import absolute_import, unicode_literals

from corehq.util.django_migrations import skip_on_fresh_install

MIGRATION_MESSAGE = """
Before you can merge you must run the {slug} doc_type migration.

If you're seeing this on your **dev machine**, run

./manage.py sync_couch_views
./manage.py run_doctype_migration {slug} --initial
./manage.py migrate

and that final migrate should go through without a hitch.

After you migrate/update your code and everything's working fine, run

./manage.py run_doctype_migration {slug} --cleanup

to delete the documents from the source db that have been copied to the target db


If you're seeing this on a **production deploy**
take note of the full file path to this aborted release,
something like "/home/cchq/www/production/releases/2015-10-16_19.37",
and then follow the full instructions for the zero-downtime live swap:

https://github.com/dimagi/commcare-hq/blob/master/corehq/doctypemigrations/README.md#run-the-doctype-migration

Instead of the "current" release, use the path to this release.
(This simply has the effect of running the process on up-to-date code.)

NOTE: If you are seeing this on a fresh install of CommCareHQ, then you can
ignore the above. Instead, the first time you run migrate, run it with the
following command (this command assumes a linux environment - for other platforms
you just need to run python manage.py migrate with a temporary environment
variable CCHQ_IS_FRESH_INSTALL set to 1):
    env CCHQ_IS_FRESH_INSTALL=1 python manage.py migrate
"""


class MigrationNotComplete(Exception):
    pass


def assert_initial_complete(migrator):
    @skip_on_fresh_install
    def forwards(apps, schema_editor):
        if not migrator.last_seq:
            raise MigrationNotComplete(MIGRATION_MESSAGE.format(slug=migrator.slug))
    return forwards
