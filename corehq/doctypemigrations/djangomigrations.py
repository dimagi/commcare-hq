from django.conf import settings


MIGRATION_MESSAGE = """
Before you can merge you must run the {slug} doc_type migration.

To do so, run

./manage.py run_doctype_migration {slug} --initial

In production you should then run

./manage.py run_doctype_migration {slug} --continuous

and deploy while that is running. (You don't need to do this locally.)

Then rerun

./manage.py migrate

or re-deploy and that should go smoothly.


After you migrate/update your code and everything's working fine, run

./manage.py run_doctype_migration {slug} --cleanup

to delete the documents from the source db that have been copied to the target db

"""


class MigrationNotComplete(Exception):
    pass


def assert_initial_complete(migrator):
    def forwards(apps, schema_editor):
        if not migrator.last_seq and not settings.UNIT_TESTING:
            raise MigrationNotComplete(MIGRATION_MESSAGE.format(slug=migrator.slug))
    return forwards
