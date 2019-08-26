
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0007_index_indicator_config_ids'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop, elidable=True),
    ]
