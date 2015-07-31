# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FacilityInCharge',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_id', models.CharField(max_length=128, db_index=True)),
                ('location', models.ForeignKey(to='locations.SQLLocation')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
