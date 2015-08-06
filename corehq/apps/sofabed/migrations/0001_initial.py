# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CaseActionData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('index', models.IntegerField()),
                ('action_type', models.CharField(max_length=64, db_index=True)),
                ('user_id', models.CharField(max_length=128, null=True, db_index=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('server_date', models.DateTimeField(null=True)),
                ('xform_id', models.CharField(max_length=128, null=True)),
                ('xform_xmlns', models.CharField(max_length=128, null=True)),
                ('sync_log_id', models.CharField(max_length=128, null=True)),
                ('domain', models.CharField(max_length=128, null=True, db_index=True)),
                ('case_owner', models.CharField(max_length=128, null=True, db_index=True)),
                ('case_type', models.CharField(max_length=128, null=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CaseData',
            fields=[
                ('case_id', models.CharField(max_length=128, unique=True, serialize=False, primary_key=True)),
                ('domain', models.CharField(max_length=128, db_index=True)),
                ('version', models.CharField(max_length=10, null=True)),
                ('type', models.CharField(max_length=128, null=True, db_index=True)),
                ('closed', models.BooleanField(default=False, db_index=True)),
                ('user_id', models.CharField(max_length=128, null=True, db_index=True)),
                ('owner_id', models.CharField(max_length=128, null=True, db_index=True)),
                ('opened_on', models.DateTimeField(null=True, db_index=True)),
                ('opened_by', models.CharField(max_length=128, null=True, db_index=True)),
                ('closed_on', models.DateTimeField(null=True, db_index=True)),
                ('closed_by', models.CharField(max_length=128, null=True, db_index=True)),
                ('modified_on', models.DateTimeField(db_index=True)),
                ('modified_by', models.CharField(max_length=128, null=True)),
                ('server_modified_on', models.DateTimeField(null=True, db_index=True)),
                ('name', models.CharField(max_length=512, null=True)),
                ('external_id', models.CharField(max_length=128, null=True)),
                ('case_owner', models.CharField(max_length=128, null=True, db_index=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CaseIndexData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('identifier', models.CharField(max_length=64, db_index=True)),
                ('referenced_type', models.CharField(max_length=64, db_index=True)),
                ('referenced_id', models.CharField(max_length=128, db_index=True)),
                ('case', models.ForeignKey(related_name='indices', to='sofabed.CaseData')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FormData',
            fields=[
                ('domain', models.CharField(max_length=255, db_index=True)),
                ('received_on', models.DateTimeField(db_index=True)),
                ('instance_id', models.CharField(max_length=255, unique=True, serialize=False, primary_key=True)),
                ('time_start', models.DateTimeField()),
                ('time_end', models.DateTimeField(db_index=True)),
                ('duration', models.BigIntegerField()),
                ('device_id', models.CharField(max_length=255, null=True)),
                ('user_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('username', models.CharField(max_length=255, null=True)),
                ('app_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('xmlns', models.CharField(max_length=1000, null=True, db_index=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='caseactiondata',
            name='case',
            field=models.ForeignKey(related_name='actions', to='sofabed.CaseData'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='caseactiondata',
            unique_together=set([('case', 'index')]),
        ),
    ]
