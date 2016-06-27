# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0035_kill_date_received'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='skip_invoicing_if_no_feature_charges',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
