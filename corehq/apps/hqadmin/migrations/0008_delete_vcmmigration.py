# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
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
