# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0019_remove_softwareplanversion_product_rates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='softwareplanversion',
            name='product_rate',
            field=models.ForeignKey(to='accounting.SoftwareProductRate'),
            preserve_default=True,
        ),
    ]
