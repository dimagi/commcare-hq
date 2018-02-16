# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0002_auto_20160420_2105'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqllocation',
            name='_products',
            field=models.ManyToManyField(to='products.SQLProduct'),
        ),
    ]
