# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0002_auto_20160219_0951'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='usererrorentry',
            index_together=set([('domain', 'app_id', 'version_number')]),
        ),
    ]
