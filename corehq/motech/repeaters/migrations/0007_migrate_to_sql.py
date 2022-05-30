import sys
import traceback

from django.core.management import call_command
from django.db import migrations
from corehq.motech.repeaters.models import Repeater

from corehq.util.django_migrations import skip_on_fresh_install


COUNT_ITEMS_TO_BE_MIGRATED = "SELECT COUNT(*) FROM repeaters_repeater where is_deleted=False"
GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "a6c1ae61ee02550b35389785d1f1fd2023186db6"
AUTO_MIGRATE_ITEMS_LIMIT = 10000
AUTO_MIGRATE_FAILED_MESSAGE = """
A migration must be performed before this environment can be upgraded to the
latest version of CommCareHQ. Instructions for running the migration can be
found at this link:

https://github.com/dimagi/commcare-cloud/blob/master/docs/changelog/0000-example-entry.md

You will need to checkout an older version of CommCareHQ first if you are
unable to run the management command because it has been deleted:

git checkout {commit}
""".format(commit=GIT_COMMIT_WITH_MANAGEMENT_COMMAND)


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):
    """Check if migrated. Raises SystemExit if not migrated"""
    num_items = count_items_to_be_migrated(schema_editor.connection)
    print(f"Starting to migrate {num_items}")
    migrated = num_items == 0
    if migrated:
        return

    if num_items < AUTO_MIGRATE_ITEMS_LIMIT:
        try:
            call_command(
                "migrate_all_repeaters",
            )
            migrated_to_be = count_items_to_be_migrated(schema_editor.connection)
            print(f"After migrations {migrated_to_be}")
            migrated = migrated_to_be == 0
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


def get_all_repeaters_count():
    return Repeater.get_db().view('repeaters/repeaters', reduce=False, include_docs=False).count()


def count_items_to_be_migrated(connection):
    """Return the number of items that need to be migrated"""
    couch_repeater_count = get_all_repeaters_count()
    with connection.cursor() as cursor:
        cursor.execute(COUNT_ITEMS_TO_BE_MIGRATED)
        sql_repeater_count = cursor.fetchone()[0]
        return couch_repeater_count - sql_repeater_count


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0006_add_proxy_models'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
