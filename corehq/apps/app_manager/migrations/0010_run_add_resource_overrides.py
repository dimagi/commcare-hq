from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_overrides_for_all_builds(apps, schema_editor):
    call_command('add_resource_overrides')


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0009_resourceoverride'),
    ]

    operations = [
        migrations.RunPython(_add_overrides_for_all_builds,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
