import sys
import traceback

from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install
from corehq.toggles import TABLEAU_USER_SYNCING
from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    get_migration_status,
    set_migration_complete,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.exceptions import (
    DomainMigrationProgressError,
)
from corehq.apps.domain_migration_flags.models import MigrationStatus
from corehq.apps.users.models import UserRole

MIGRATION_SLUG = "mirror_web_users_permissions_to_tableau_config_permissions"
AUTO_MIGRATE_FAILED_MESSAGE = """
This migration cannot be performed automatically and must instead be run manually
before this environment can be upgraded to the latest version of CommCare HQ.
Instructions for running the migration can be found at this link:

https://commcare-cloud.readthedocs.io/en/latest/changelog/0081-copy_web_user_permissions_to_tableau_config_permission.html
"""


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):

    def transfer_web_user_permission_to_tableau_config_permission():
        status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if status == MigrationStatus.COMPLETE:
            print("Manage Tableau Configuration permissions have already been populated from Web Users permissons")
            return
        if status not in (MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE):
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        for role in UserRole.objects.filter(domain__in=TABLEAU_USER_SYNCING.get_enabled_domains()):
            permissions = role.permissions
            if permissions.edit_web_users:
                permissions.edit_user_tableau_config = True
                permissions.view_user_tableau_config = True
            elif permissions.view_web_users:
                permissions.view_user_tableau_config = True

            role.set_permissions(permissions.to_list())

        try:
            set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
        except DomainMigrationProgressError:
            raise

    try:
        transfer_web_user_permission_to_tableau_config_permission()
    except Exception:
        traceback.print_exc()
        print("")
        print(AUTO_MIGRATE_FAILED_MESSAGE)
        sys.exit(1)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0064_add_edit_view_tableau_config_permissions'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
