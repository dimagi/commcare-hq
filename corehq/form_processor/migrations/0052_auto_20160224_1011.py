# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0051_auto_20160224_0922'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id', 'type')]),
        ),
    ]
