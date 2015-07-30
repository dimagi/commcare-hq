# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PillowError',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('doc_id', models.CharField(max_length=255, db_index=True)),
                ('pillow', models.CharField(max_length=255)),
                ('date_created', models.DateTimeField()),
                ('date_last_attempt', models.DateTimeField()),
                ('date_next_attempt', models.DateTimeField(null=True, db_index=True)),
                ('total_attempts', models.IntegerField(default=0)),
                ('current_attempt', models.IntegerField(default=0, db_index=True)),
                ('error_type', models.CharField(max_length=255, null=True)),
                ('error_traceback', models.TextField(null=True)),
                ('change', models.TextField(null=True)),
                ('domains', models.CharField(max_length=255, null=True, db_index=True)),
                ('doc_type', models.CharField(max_length=255, null=True, db_index=True)),
                ('doc_date', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='pillowerror',
            unique_together=set([('doc_id', 'pillow')]),
        ),
    ]
