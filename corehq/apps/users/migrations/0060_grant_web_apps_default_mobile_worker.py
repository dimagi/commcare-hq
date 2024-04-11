# Gives the default mobile worker role access to web apps
from django.db import migrations

from corehq.apps.users.models_role import UserRole
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _update_default_mobile_worker_role(apps, schema_editor):
    for role in UserRole.objects.filter(is_commcare_user_default=True):
        permissions = role.permissions
        permissions.access_web_apps = True
        permissions.normalize(previous=role.permissions)
        role.set_permissions(permissions.to_list())


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0059_add_web_apps_groups_permission_flag'),
    ]

    operations = [
        migrations.RunPython(_update_default_mobile_worker_role, migrations.RunPython.noop)
    ]
