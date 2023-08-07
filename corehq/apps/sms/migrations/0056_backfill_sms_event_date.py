import sys
import traceback

from django.core.management import call_command, get_commands
from django.db import migrations

from corehq.apps.domain_migration_flags.api import get_migration_complete, ALL_DOMAINS
from corehq.apps.sms.management.commands.backfill_sms_subevent_date import MIGRATION_SLUG
from corehq.util.django_migrations import skip_on_fresh_install


COUNT_ITEMS_TO_BE_MIGRATED = "SELECT COUNT(*) FROM sms_messagingsubevent WHERE date_last_activity is null"
GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "896676ba3c3b7f5e2898f055ace3ee1b196a7fac"
AUTO_MIGRATE_ITEMS_LIMIT = 200000
AUTO_MIGRATE_COMMAND_NAME = "backfill_sms_subevent_date"
AUTO_MIGRATE_FAILED_MESSAGE = """
This migration cannot be performed automatically and must instead be run manually
before this environment can be upgraded to the latest version of CommCare HQ.
Instructions for running the migration can be found at this link:

https://commcare-cloud.readthedocs.io/en/latest/changelog/0063-backfill_sms_event_data_for_api_performance.html
"""
AUTO_MIGRATE_COMMAND_MISSING_MESSAGE = """
You will need to checkout an older version of CommCare HQ before you can perform this migration
because the management command has been removed.

git checkout {commit}
""".format(commit=GIT_COMMIT_WITH_MANAGEMENT_COMMAND)


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):
    """Check if migrated. Raises SystemExit if not migrated"""
    if get_migration_complete(ALL_DOMAINS, MIGRATION_SLUG):
        return

    num_items = count_items_to_be_migrated(schema_editor.connection)

    migrated = num_items == 0
    if migrated:
        return

    if AUTO_MIGRATE_COMMAND_NAME not in get_commands():
        print("")
        print(AUTO_MIGRATE_FAILED_MESSAGE)
        print(AUTO_MIGRATE_COMMAND_MISSING_MESSAGE)
        sys.exit(1)

    if num_items < AUTO_MIGRATE_ITEMS_LIMIT:
        try:
            call_command(AUTO_MIGRATE_COMMAND_NAME)
            migrated = count_items_to_be_migrated(schema_editor.connection) == 0
            if not migrated:
                print("Automatic migration failed")
        except Exception:
            traceback.print_exc()
    else:
        print("Found %s items that need to be migrated." % num_items)
        print("Too many to migrate automatically.")

    if not migrated:
        print("")
        print(AUTO_MIGRATE_FAILED_MESSAGE)
        sys.exit(1)


def count_items_to_be_migrated(connection):
    """Return the number of items that need to be migrated"""
    with connection.cursor() as cursor:
        cursor.execute(COUNT_ITEMS_TO_BE_MIGRATED)
        return cursor.fetchone()[0]


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0055_messagingsubevent_index_domain_date_id'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
