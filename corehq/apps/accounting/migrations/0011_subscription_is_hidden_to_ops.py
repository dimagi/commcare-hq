# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0010_add_do_not_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='is_hidden_to_ops',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
