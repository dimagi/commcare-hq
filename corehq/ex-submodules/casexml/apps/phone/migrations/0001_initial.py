# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='OwnershipCleanlinessFlag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100, db_index=True)),
                ('owner_id', models.CharField(max_length=100, db_index=True)),
                ('is_clean', models.BooleanField(default=False)),
                ('last_checked', models.DateTimeField()),
                ('hint', models.CharField(max_length=100, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='ownershipcleanlinessflag',
            unique_together=set([('domain', 'owner_id')]),
        ),
    ]
