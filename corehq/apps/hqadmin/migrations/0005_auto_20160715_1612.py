
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0004_auto_20160715_1547'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vcmmigration',
            name='domain',
            field=models.CharField(unique=True, max_length=255),
            preserve_default=True,
        ),
    ]
