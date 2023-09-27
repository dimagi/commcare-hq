from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _delete_xml(apps, schema_editor):
    call_command("delete_case_list_custom_variables_xml", "--start-from-scratch", "--failfast", "--force-run-again")


@skip_on_fresh_install
def _recreate_xml(apps, schema_editor):
    call_command(
        "delete_case_list_custom_variables_xml", "--start-from-scratch", "--failfast", "--reverse", "--force-run-again")


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0027_add_case_tile_template_field'),
    ]

    operations = [
        migrations.RunPython(
            _delete_xml,
            reverse_code=_recreate_xml,
        ),
    ]
