from django.db import migrations

from architect.commands import partition


def add_partitions(apps, schema_editor):
    partition.run({'module': 'corehq.apps.data_interfaces.models'})


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0041_clear_bulkasyncjob'),
    ]

    operations = [
        migrations.RunPython(add_partitions, migrations.RunPython.noop),
    ]
