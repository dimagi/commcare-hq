# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.util.django_migrations import AlterIndexIfNotExists


class Migration(migrations.Migration):

    dependencies = [
        ('phonelog', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicereportentry',
            name='device_id',
            field=models.CharField(max_length=50, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='devicereportentry',
            name='domain',
            field=models.CharField(max_length=100),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='devicereportentry',
            name='user_id',
            field=models.CharField(max_length=50, null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='devicereportentry',
            name='username',
            field=models.CharField(max_length=100, null=True),
            preserve_default=True,
        ),
        AlterIndexIfNotExists(
            name='devicereportentry',
            index_together=set([('domain', 'device_id'), ('domain', 'date'), ('domain', 'username')]),
        ),
    ]
