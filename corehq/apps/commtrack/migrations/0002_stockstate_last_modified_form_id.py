# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commtrack', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockstate',
            name='last_modified_form_id',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
    ]
