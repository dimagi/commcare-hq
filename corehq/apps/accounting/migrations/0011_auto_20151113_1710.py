# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0010_billingaccount_pre_or_post_pay'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingaccount',
            name='pre_or_post_pay',
            field=models.CharField(default=b'NOT_SET', max_length=25, choices=[(b'PREPAY', b'Prepay'), (b'POSTPAY', b'Postpay')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='subscription',
            name='service_type',
            field=models.CharField(default=b'NOT_SET', max_length=25, choices=[(b'IMPLEMENTATION', b'Implementation'), (b'PRODUCT', b'Product'), (b'TRIAL', b'Trial'), (b'SANDBOX', b'Sandbox'), (b'INTERNAL', b'Internal')]),
            preserve_default=True,
        ),
    ]
