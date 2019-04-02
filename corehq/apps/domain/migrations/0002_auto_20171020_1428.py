# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2017-10-20 14:28
from __future__ import unicode_literals
from __future__ import absolute_import
from architect.commands import partition

from django.db import migrations, models



def add_partitions(apps, schema_editor):
    partition.run({'module': 'corehq.apps.domain.models'})


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuperuserProjectEntryRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.EmailField(db_index=True, max_length=254)),
                ('domain', models.CharField(max_length=256)),
                ('last_login', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AlterIndexTogether(
            name='superuserprojectentryrecord',
            index_together=set([('domain', 'username')]),
        ),
        migrations.RunPython(add_partitions),
    ]
