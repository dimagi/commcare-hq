# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0046_auto_20151126_1351'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
            preserve_default=True,
        ),
    ]
