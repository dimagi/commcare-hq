# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripePaymentMethod',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('accounting.paymentmethod',),
        ),
        migrations.AddField(
            model_name='billingaccount',
            name='auto_pay_user',
            field=models.CharField(max_length=80, null=True),
            preserve_default=True,
        ),
    ]
