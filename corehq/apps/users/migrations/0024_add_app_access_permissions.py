import sys
import traceback

from django.core.management import call_command
from django.db import migrations

from dimagi.utils.couch.database import iter_docs

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install

GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "2a53b5901a0a1e353a6fa078919fe0d6f071eff0"
AUTO_MIGRATE_ITEMS_LIMIT = 1000
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
    num_items = count_items_to_be_migrated()

    migrated = num_items == 0
    if migrated:
        return

    if num_items < AUTO_MIGRATE_ITEMS_LIMIT:
        try:
            call_command(
                "copy_web_permissions_to_all_apps"
            )
            migrated = count_items_to_be_migrated() == 0
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


def count_items_to_be_migrated():
    """Return the number of items that need to be migrated"""
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    counter = 0
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        counter = False
        permissions = role_doc['permissions']
        if (
            permissions.get('access_all_apps') != permissions.get('view_web_apps')
            or permissions.get('allowed_app_list') != permissions.get('view_web_apps_list')
        ):
            counter += 1
        return counter


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0023_hqapikey_role_id'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
