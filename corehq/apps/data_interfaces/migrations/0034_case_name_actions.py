from django.db import migrations
from corehq.apps.data_interfaces.models import CaseDeduplicationActionDefinition


def forwards(apps, schema_editor):
    replace_property_value('case_name', 'name')


def backwards(apps, schema_editor):
    replace_property_value('name', 'case_name')


def replace_property_value(old_value, new_value):
    actions = CaseDeduplicationActionDefinition.objects.filter(case_properties__contains=[old_value])
    for action in actions:
        action.case_properties = [
            new_value if value == old_value else value
            for value in action.case_properties
        ]

        action.save()


class Migration(migrations.Migration):
    dependencies = [
        ('data_interfaces', '0033_automaticupdaterule_deleted_on'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
