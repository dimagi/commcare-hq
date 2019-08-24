
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0002_vcmmigrationaudit'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='VCMMigrationAudit',
            new_name='VCMMigration',
        ),
    ]
