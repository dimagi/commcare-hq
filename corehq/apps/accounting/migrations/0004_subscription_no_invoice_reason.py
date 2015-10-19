# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0003_bootstrap'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='no_invoice_reason',
            field=models.CharField(max_length=256, null=True, blank=True),
            preserve_default=True,
        ),
    ]
