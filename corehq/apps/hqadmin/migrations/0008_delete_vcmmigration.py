# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0007_esrestorepillowcheckpoint_datefield'),
    ]

    operations = [
        migrations.DeleteModel(
            name='VCMMigration',
        ),
    ]
