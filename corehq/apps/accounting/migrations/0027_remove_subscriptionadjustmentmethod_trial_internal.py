# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0026_subscriber_domain_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriptionadjustment',
            name='method',
            field=models.CharField(default=b'INTERNAL', max_length=50, choices=[(b'USER', b'User'), (b'INTERNAL', b'Ops'), (b'TASK', b'Task (Invoicing)'), (b'TRIAL', b'30 Day Trial')]),
            preserve_default=True,
        ),
    ]
