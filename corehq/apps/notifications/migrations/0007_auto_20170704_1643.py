# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-07-04 16:43
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0006_add_billing_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='DismissedUINotify',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(db_index=True, max_length=140)),
                ('date_dismissed', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='dismisseduinotify',
            unique_together=set([('user', 'slug')]),
        ),
    ]
