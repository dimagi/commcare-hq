
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0055_daily_consumption'),
    ]

    operations = [
        migrations.AddField(
            model_name='ledgervalue',
            name='last_modified_form_id',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
    ]
