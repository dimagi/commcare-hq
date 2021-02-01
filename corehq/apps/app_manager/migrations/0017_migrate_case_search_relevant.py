from django.core.management import call_command
from django.db import migrations

from corehq.toggles import SYNC_SEARCH_CASE_CLAIM
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_case_search_relevant(apps, schema_editor):
    for domain in sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains()):
        call_command('migrate_case_search_relevant', domain=domain)


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0016_alter_exchangeapplication'),
    ]

    operations = [
        migrations.RunPython(_migrate_case_search_relevant,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
