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


MIGRATION_SLUG = "mirror_web_users_permissions_to_tableau_config_permissions"


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):
    UserRole = apps.get_model('users', 'UserRole')
    Permission = apps.get_model('users', 'Permission')

    def transfer_web_user_permission_to_tableau_config_permission():
        status = get_migration_status(ALL_DOMAINS, MIGRATION_SLUG)
        if status == MigrationStatus.COMPLETE:
            print("Manage Tableau Configuration permissions have already been populated from Web Users permissons")
            return
        if status not in (MigrationStatus.IN_PROGRESS, MigrationStatus.COMPLETE):
            set_migration_started(ALL_DOMAINS, MIGRATION_SLUG)

        edit_web_users_permission = Permission.objects.get(value='edit_web_users')
        view_web_users_permission = Permission.objects.get(value='view_web_users')
        edit_user_tableau_config_permission = Permission.objects.get(value='edit_user_tableau_config')
        view_user_tableau_config_permission = Permission.objects.get(value='view_user_tableau_config')

        for role in UserRole.objects.filter(domain__in=TABLEAU_USER_SYNCING.get_enabled_domains()):
            has_edit_web_users_permission = role.rolepermission_set.filter(permission_fk=edit_web_users_permission).exists()
            has_view_web_users_permission = role.rolepermission_set.filter(permission_fk=view_web_users_permission).exists()

            if has_edit_web_users_permission:
                role.rolepermission_set.get_or_create(permission_fk=edit_user_tableau_config_permission, defaults={"allow_all": True})
                role.rolepermission_set.get_or_create(permission_fk=view_user_tableau_config_permission, defaults={"allow_all": True})
            elif has_view_web_users_permission:
                role.rolepermission_set.get_or_create(permission_fk=view_user_tableau_config_permission, defaults={"allow_all": True})

        try:
            set_migration_complete(ALL_DOMAINS, MIGRATION_SLUG)
        except DomainMigrationProgressError:
            raise

    try:
        transfer_web_user_permission_to_tableau_config_permission()
    except Exception:
        traceback.print_exc()
        print("")
        print("Auto migrate failed")
        sys.exit(1)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0064_add_edit_view_tableau_config_permissions'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
