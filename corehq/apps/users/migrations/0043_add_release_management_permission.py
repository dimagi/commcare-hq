from django.db import migrations

from corehq.apps.users.models_role import Permission


def create_release_management_permission(apps, schema_editor):
    """
    This is the only permission-related migration that intentionally does not
    get skipped on fresh install  (no @skip_on_fresh_install decorator). This
    is to ensure that we have a migration that will run Permission.create_all()
    on a fresh install to eagerly populate all HqPermissions in the postgres
    table.
    """
    Permission.create_all()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0042_deactivatemobileworkertrigger'),
        # Permission is an audited table that will create audit events
        ('field_audit', '0002_add_is_bootstrap_column'),
    ]

    operations = [
        migrations.RunPython(create_release_management_permission, migrations.RunPython.noop)
    ]
