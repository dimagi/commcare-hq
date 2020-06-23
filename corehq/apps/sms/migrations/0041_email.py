# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-06-16 13:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0040_remove_karix_backend'),
    ]

    operations = [
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('date', models.DateTimeField(db_index=True)),
                ('couch_recipient_doc_type', models.CharField(db_index=True, max_length=126)),
                ('couch_recipient', models.CharField(db_index=True, max_length=126)),
                ('recipient_address', models.CharField(db_index=True, max_length=255)),
                ('subject', models.TextField(null=True)),
                ('body', models.TextField(null=True)),
                ('messaging_subevent', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='sms.MessagingSubEvent')),
            ],
        ),
    ]
