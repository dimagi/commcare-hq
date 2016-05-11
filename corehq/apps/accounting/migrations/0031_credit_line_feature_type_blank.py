# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0030_remove_softwareplan_visibility_trial_internal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditline',
            name='feature_type',
            field=models.CharField(blank=True, max_length=10, null=True, choices=[(b'User', b'User'), (b'SMS', b'SMS')]),
            preserve_default=True,
        ),
    ]
