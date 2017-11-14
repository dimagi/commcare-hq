# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0001_squashed_0002_auto_20161116_2209'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetype',
            name='description',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='caseproperty',
            name='description',
            field=models.TextField(default=b''),
        ),
        migrations.AlterField(
            model_name='caseproperty',
            name='name',
            field=models.CharField(default=None, max_length=255),
        ),
        migrations.AlterField(
            model_name='caseproperty',
            name='type',
            field=models.CharField(default=b'', max_length=20, choices=[(b'date', b'Date'), (b'plain', b'Plain'), (b'number', b'Number'), (b'select', b'Select'), (b'integer', b'Integer'), (b'', b'No Type Currently Selected')]),
        ),
        migrations.AlterField(
            model_name='casetype',
            name='domain',
            field=models.CharField(default=None, max_length=255),
        ),
        migrations.AlterField(
            model_name='casetype',
            name='name',
            field=models.CharField(default=None, max_length=255),
        ),
    ]
