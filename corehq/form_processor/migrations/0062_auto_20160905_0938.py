# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0061_blob_bucket'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xforminstancesql',
            name='xmlns',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
    ]
