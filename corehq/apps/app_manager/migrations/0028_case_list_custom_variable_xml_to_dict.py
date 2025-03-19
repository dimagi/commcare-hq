from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _xml_to_dict(apps, schema_editor):
    call_command("migrate_case_list_custom_variables", "--start-from-scratch", "--failfast", "--force-run-again")


@skip_on_fresh_install
def _dict_to_xml(apps, schema_editor):
    call_command(
        "migrate_case_list_custom_variables", "--start-from-scratch", "--failfast", "--reverse", "--force-run-again")


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0027_add_case_tile_template_field'),
    ]

    operations = [
        migrations.RunPython(
            _xml_to_dict,
            reverse_code=_dict_to_xml,
        ),
    ]
