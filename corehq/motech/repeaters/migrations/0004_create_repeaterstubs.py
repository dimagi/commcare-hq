from django.db import migrations

from ..migration_functions import create_repeaterstubs


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0003_migrate_connectionsettings'),
    ]

    operations = [
        migrations.RunPython(create_repeaterstubs,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
