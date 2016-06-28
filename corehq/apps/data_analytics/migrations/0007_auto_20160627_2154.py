# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_analytics', '0006_unique_girrow'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='girrow',
            index_together=set([('domain_name', 'month')]),
        ),
    ]
