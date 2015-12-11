# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0009_add_extended_trial_subscription_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='do_not_email',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        # this one was left out earlier, just involves adding validation
        migrations.AlterField(
            model_name='lineitem',
            name='quantity',
            field=models.IntegerField(default=1, validators=[django.core.validators.MaxValueValidator(2147483647), django.core.validators.MinValueValidator(-2147483648)]),
            preserve_default=True,
        ),
    ]
