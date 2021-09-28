# -*- coding: utf-8 -*-
from django.db import migrations, models

from corehq.sql_db.migrations import partitioned


@partitioned
class Migration(migrations.Migration):

    dependencies = [
        ('blobs', '0010_auto_20191023_0938'),
    ]

    operations = [
        migrations.AddField(
            model_name='blobmeta',
            name='compressed_length',
            field=models.BigIntegerField(null=True),
        ),
    ]
