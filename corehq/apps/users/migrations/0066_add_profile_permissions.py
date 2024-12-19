import sys
import traceback
from corehq.apps.users.models_role import Permission
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked
from django.db import migrations

MIGRATION_SLUG = "default_profile_permissions_on_for_existing_roles"


@skip_on_fresh_install
def create_profile_permissions(apps, schema_editor):
    Permission.create_all()


def _assert_migrated(apps, schema_editor):
    UserRole = apps.get_model('users', 'UserRole')
    Permission = apps.get_model('users', 'Permission')

    def default_profile_permissions_on_for_existing_roles():
        # All existing roles should be allowed to edit profiles since that was the default behavior
        edit_user_profile = Permission.objects.get(value='edit_user_profile')
        for chunk in with_progress_bar(chunked(UserRole.objects.values_list('id', flat=True).iterator(), 1000),
                                       length=UserRole.objects.count()):
            for role in UserRole.objects.filter(id__in=chunk):
                role.rolepermission_set.get_or_create(permission_fk=edit_user_profile, defaults={"allow_all": True})

    try:
        default_profile_permissions_on_for_existing_roles()
    except Exception:
        traceback.print_exc()
        print("")
        print("Migration failed.")
        sys.exit(1)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0065_transfer_to_tableau_config_permission'),
    ]

    operations = [
        migrations.RunPython(create_profile_permissions, migrations.RunPython.noop),
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop)
    ]
