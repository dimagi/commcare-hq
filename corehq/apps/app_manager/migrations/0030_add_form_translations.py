from django.core.management import call_command
from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install


class Migration(migrations.Migration):

    @skip_on_fresh_install
    def _populate_form_translation_fields(apps, schema_editor):
        call_command("add_form_translation_fields")

    dependencies = [
        ('app_manager', '0029_delete_case_list_custom_variable_xml'),
    ]

    operations = [
        migrations.RunPython(
            _populate_form_translation_fields,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
