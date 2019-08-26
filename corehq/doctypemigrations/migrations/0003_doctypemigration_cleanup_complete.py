
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctypemigrations', '0002_auto_20150924_1930'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctypemigration',
            name='cleanup_complete',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
