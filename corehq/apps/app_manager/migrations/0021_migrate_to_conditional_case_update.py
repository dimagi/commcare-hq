
from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install

# App manager and possibly form submission may be broken if the data models are updated but this
# migration has not been applied.


@skip_on_fresh_install
def _migrate_to_conditional_case_update(apps, schema_editor):
    call_command('migrate_to_conditional_case_update')


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0020_exchangeapplication_allow_blank_privilege'),
    ]

    operations = [
        migrations.RunPython(_migrate_to_conditional_case_update,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
