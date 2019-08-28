
from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0021_add_keyword'),
    ]

    operations = [
        migrations.AddField(
            model_name='keyword',
            name='last_modified',
            field=models.DateTimeField(default=datetime.datetime(2016, 12, 19, 0, 0, 0), auto_now=True),
            preserve_default=False,
        ),
    ]
