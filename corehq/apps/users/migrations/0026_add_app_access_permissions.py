import sys
import traceback

from django.core.management import call_command
from django.db import migrations

from couchdbkit import ResourceNotFound

from dimagi.utils.couch.database import iter_docs
from toggle.models import Toggle
from toggle.shortcuts import parse_toggle

from corehq.apps.users.models import UserRole
from corehq.util.django_migrations import skip_on_fresh_install

GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "a696ade5259cc5d95bc9a64cc0a2644ef3e56a92"
AUTO_MIGRATE_ITEMS_LIMIT = 1000
AUTO_MIGRATE_FAILED_MESSAGE = """
A migration must be performed before this environment can be upgraded to the
latest version of CommCareHQ. You should run the following management command

python manage.py copy_web_permissions_to_all_apps

You will need to checkout an older version of CommCareHQ first if you are
unable to run the management command because it has been deleted:

git checkout {commit}
""".format(commit=GIT_COMMIT_WITH_MANAGEMENT_COMMAND)


def copy_toggles(from_toggle_id, to_toggle_id):
    """
    Copies all enabled items from one toggle to another.
    """
    try:
        from_toggle = Toggle.get(from_toggle_id)
    except ResourceNotFound:
        # if no source found this is a noop
        return
    try:
        to_toggle = Toggle.get(to_toggle_id)
    except ResourceNotFound:
        to_toggle = Toggle(slug=to_toggle_id, enabled_users=[])

    for item in from_toggle.enabled_users:
        if item not in to_toggle.enabled_users:
            to_toggle.enabled_users.append(item)
            namespace, item = parse_toggle(item)

    to_toggle.save()


def _count_items_to_be_migrated():
    """Return the number of items that need to be migrated"""
    roles = UserRole.view(
        'users/roles_by_domain',
        include_docs=False,
        reduce=False
    ).all()
    counter = 0
    for role_doc in iter_docs(UserRole.get_db(), [r['id'] for r in roles]):
        UserRole.wrap(role_doc)
        permissions = role_doc['permissions']
        if (
            permissions.get('access_all_apps') != permissions.get('view_web_apps')
            or permissions.get('allowed_app_list') != permissions.get('view_web_apps_list')
        ):
            counter += 1
    return counter


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):
    """Check if migrated. Raises SystemExit if not migrated"""
    num_items = _count_items_to_be_migrated()

    migrated = num_items == 0
    if migrated:
        return

    if num_items < AUTO_MIGRATE_ITEMS_LIMIT:
        try:
            call_command(
                "copy_web_permissions_to_all_apps"
            )
            migrated = _count_items_to_be_migrated() == 0
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


@skip_on_fresh_install
def _migrate_toggles(apps, schema_editor):
    from_toggle_slug = 'role_webapps_permissions'
    to_toggle_slug = 'role_app_access_permissions'
    copy_toggles(from_toggle_slug, to_toggle_slug)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0025_hqapikey_domain'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop),
        migrations.RunPython(_migrate_toggles, migrations.RunPython.noop),
    ]
