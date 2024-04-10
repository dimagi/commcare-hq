from django import VERSION as django_version
from django.db import migrations, models

# Django < 4 specifies related_name in ManyToManyField, whereas Django >= 4 does not.
# This results in a new migration being created on 4. This m2m_kwargs is designed to enable
# upgrading to Django 4.2 from 3.2 smoothly.
m2m_kwargs = {}
if django_version[0] < 4:
    m2m_kwargs['related_name'] = '_caseduplicate_potential_duplicates_+'


class Migration(migrations.Migration):

    dependencies = [
        ("data_interfaces", "0037_add_dedupe_update_toggle"),
    ]

    state_operations = [
        migrations.AlterField(
            model_name="caseduplicate",
            name="potential_duplicates",
            field=models.ManyToManyField(to="data_interfaces.caseduplicate", **m2m_kwargs),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
