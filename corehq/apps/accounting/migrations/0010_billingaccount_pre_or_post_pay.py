# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0009_auto_20151111_2253'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingaccount',
            name='pre_or_post_pay',
            field=models.CharField(default=b'POSTPAY', max_length=25, choices=[(b'PREPAY', b'Prepay'), (b'POSTPAY', b'Postpay')]),
            preserve_default=True,
        ),
    ]
