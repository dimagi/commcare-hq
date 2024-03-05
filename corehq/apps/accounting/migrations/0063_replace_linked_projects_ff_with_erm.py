from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_linked_projects_ff_to_erm(apps, schema_editor):
    call_command('migrate_feature_flag_domains')


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0062_add_release_management_to_enterprise'),
        ('linked_domain', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            _migrate_linked_projects_ff_to_erm,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
