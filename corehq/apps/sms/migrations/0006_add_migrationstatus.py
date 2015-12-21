# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0005_remove_mobilebackend_unique_constraint'),
    ]

    operations = [
        migrations.CreateModel(
            name='MigrationStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=126)),
                ('timestamp', models.DateTimeField()),
            ],
            options={
                'db_table': 'messaging_migrationstatus',
            },
            bases=(models.Model,),
        ),
    ]
