# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ewsghana', '0003_ewsmigrationproblem_ewsmigrationstats'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLNotification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=128)),
                ('user_id', models.CharField(max_length=128)),
                ('type', models.CharField(max_length=128)),
                ('week', models.IntegerField()),
                ('year', models.IntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
