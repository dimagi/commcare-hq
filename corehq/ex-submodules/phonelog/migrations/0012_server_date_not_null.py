# Generated by Django 1.10.7 on 2017-06-30 15:48

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0011_partition_devicelogentry'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicereportentry',
            name='server_date',
            field=models.DateTimeField(db_index=True, default=datetime.datetime(2018, 6, 30, 0, 0, 0, 0)),
            preserve_default=False,
        ),
    ]
