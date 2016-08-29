# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0038_bootstrap_new_user_buckets'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wireinvoice',
            name='domain',
            field=models.CharField(max_length=100),
            preserve_default=True,
        ),
    ]
