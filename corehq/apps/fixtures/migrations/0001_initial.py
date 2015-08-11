# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UserFixtureStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_id', models.CharField(max_length=100, db_index=True)),
                ('fixture_type', models.PositiveSmallIntegerField(choices=[(1, b'Location')])),
                ('last_modified', models.DateTimeField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='userfixturestatus',
            unique_together=set([('user_id', 'fixture_type')]),
        ),
    ]
