# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0044_subscription_skip_auto_downgrade'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingaccount',
            name='auto_pay_user',
            field=models.CharField(max_length=80, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='billingaccount',
            name='dimagi_contact',
            field=models.EmailField(default='', max_length=254, blank=True),
            preserve_default=False,
        ),
    ]
