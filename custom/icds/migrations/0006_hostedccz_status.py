# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-23 09:39
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds', '0005_hostedccz_note'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostedccz',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'),
                                            ('building', 'Building'),
                                            ('failed', 'Failed'),
                                            ('completed', 'Completed')],
                                   default='pending', max_length=255),
        ),
    ]
