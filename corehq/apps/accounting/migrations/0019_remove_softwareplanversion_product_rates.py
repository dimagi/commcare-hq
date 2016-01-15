# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0018_datamigration_product_rates_to_product_rate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='softwareplanversion',
            name='product_rates',
        ),
    ]
