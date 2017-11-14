# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0005_casetype_fully_generated'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseproperty',
            name='group',
            field=models.TextField(default=b'', blank=True),
        ),
    ]
