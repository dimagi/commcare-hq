# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0050_fix_product_rates'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultproductplan',
            name='is_report_builder_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterUniqueTogether(
            name='defaultproductplan',
            unique_together=set([('edition', 'is_trial', 'is_report_builder_enabled')]),
        ),
    ]
