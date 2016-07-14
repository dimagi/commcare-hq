# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0038_bootstrap_new_user_buckets'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='paymentmethod',
            unique_together=set([('web_user', 'method_type')]),
        ),
    ]
