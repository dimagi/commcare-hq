# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceReportEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('xform_id', models.CharField(max_length=50, db_index=True)),
                ('i', models.IntegerField()),
                ('msg', models.TextField()),
                ('type', models.CharField(max_length=32, db_index=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('server_date', models.DateTimeField(null=True, db_index=True)),
                ('domain', models.CharField(max_length=100, db_index=True)),
                ('device_id', models.CharField(max_length=50, null=True, db_index=True)),
                ('app_version', models.TextField(null=True)),
                ('username', models.CharField(max_length=100, null=True, db_index=True)),
                ('user_id', models.CharField(max_length=50, null=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('xform_id', models.CharField(max_length=50, db_index=True)),
                ('i', models.IntegerField()),
                ('user_id', models.CharField(max_length=50)),
                ('sync_token', models.CharField(max_length=50)),
                ('username', models.CharField(max_length=100, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='userentry',
            unique_together=set([('xform_id', 'i')]),
        ),
        migrations.AlterUniqueTogether(
            name='devicereportentry',
            unique_together=set([('xform_id', 'i')]),
        ),
        migrations.AlterIndexTogether(
            name='devicereportentry',
            index_together=set([('domain', 'date')]),
        ),
    ]
