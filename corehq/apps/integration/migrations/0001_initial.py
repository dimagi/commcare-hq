# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-02-25 19:21
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SimprintsIntegration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=128, unique=True)),
                ('is_enabled', models.BooleanField(default=False)),
                ('project_id', models.CharField(max_length=255)),
                ('user_id', models.CharField(max_length=255)),
                ('module_id', models.CharField(max_length=255)),
            ],
        ),
    ]
