import sys
import traceback

from django.db import migrations
from django.db.models import Q

from dimagi.utils.chunked import chunked
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from corehq.apps.users.models import HqPermissions
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

TODO: Update with changelog link
"""


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):

    def transfer_web_user_permission_to_tableau_config_permission():
        user_role_ids_to_migrate = get_user_role_ids_to_migrate()

        status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if status == MigrationStatus.COMPLETE:
            print("Manage Tableau Configuration permissions have already been populated from Web Users permissons")
            return
        if status not in (MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE):
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        for chunk in with_progress_bar(chunked(user_role_ids_to_migrate, 1000),
                                    length=len(user_role_ids_to_migrate)):
            for role in UserRole.objects.filter(id__in=chunk):
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

    num_items = len(get_user_role_ids_to_migrate())

    migrated = num_items == 0
    if migrated:
        return

    try:
        transfer_web_user_permission_to_tableau_config_permission()
        migrated = len(get_user_role_ids_to_migrate()) == 0
        if not migrated:
            print("Automatic migration failed")
    except Exception:
        traceback.print_exc()

    if not migrated:
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


def get_user_role_ids_to_migrate():
    tableau_user_syncing_domains = TABLEAU_USER_SYNCING.get_enabled_domains()

    return (UserRole.objects
        .filter(domain__in=tableau_user_syncing_domains)
        .exclude(role_already_migrated())
        .filter(role_has_view_web_user_permission())
        .distinct()
        .values_list("id", flat=True))


def role_already_migrated() -> Q:
    return Q(rolepermission__permission_fk__value=HqPermissions.view_user_tableau_config.name)


def role_has_view_web_user_permission() -> Q:
    can_edit_web_user = Q(rolepermission__permission_fk__value=HqPermissions.edit_web_users.name)
    # Roles that can edit should also have view permission so this is redundant but I am including it just
    # for safety.
    can_view_web_user = Q(rolepermission__permission_fk__value=HqPermissions.view_web_users.name)
    return (can_edit_web_user | can_view_web_user)
