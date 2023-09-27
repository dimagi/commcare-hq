from django.db import migrations
from corehq.apps.data_interfaces.models import CaseDeduplicationActionDefinition


def forwards(apps, schema_editor):
    replace_property_value('case_name', 'name')


def backwards(apps, schema_editor):
    replace_property_value('name', 'case_name')


def replace_property_value(old_value, new_value):
    actions = CaseDeduplicationActionDefinition.objects.filter(case_properties__contains=[old_value])
    for action in actions:
        props = action.case_properties
        try:
            value_index = props.index(old_value)
        except ValueError:
            # Should never happen, but ignore these errors
            continue
        props[value_index] = new_value
        action.save()


class Migration(migrations.Migration):
    dependencies = [
        ('data_interfaces', '0033_automaticupdaterule_deleted_on'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
