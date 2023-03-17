from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _migrate_to_conditional_case_update(apps, schema_editor):
    call_command("migrate_to_conditional_case_update", "--deleted-apps-only")


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0025_migrate_to_search_filter_flag'),
    ]

    operations = [
        migrations.RunPython(
            _migrate_to_conditional_case_update,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
