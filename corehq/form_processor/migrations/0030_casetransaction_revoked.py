# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0029_drop_not_null_from_opened_on_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetransaction',
            name='revoked',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
