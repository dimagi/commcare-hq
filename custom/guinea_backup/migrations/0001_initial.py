# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from datetime import date

from django.db import models, migrations

from corehq.sql_db.operations import HqRunPython


def add_dummy_row(apps, schema_editor):
    BackupRecord = apps.get_model("guinea_backup", "BackupRecord")
    dummy = BackupRecord(last_update=date(2014, 01, 01))
    dummy.save()


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BackupRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('last_update', models.DateField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        HqRunPython(add_dummy_row),
    ]
