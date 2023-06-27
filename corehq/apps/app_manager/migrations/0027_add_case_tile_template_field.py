from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_case_tile_template_field(apps, schema_editor):
    call_command("add_case_tile_template_field", "--start-from-scratch", "--failfast")


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0026_conditional_case_update_deleted_apps'),
    ]

    operations = [
        migrations.RunPython(
            _add_case_tile_template_field,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
