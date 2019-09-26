# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-09-06 01:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('export', '0006_delete_dailysavedexportnotification'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerSectionEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('section_id', models.CharField(max_length=255)),
                ('entry_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='ledgersectionentry',
            unique_together=set([('domain', 'section_id', 'entry_id')]),
        ),
    ]
