# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Deploy',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('in_progress', models.BooleanField(default=False, db_index=True)),
                ('success', models.BooleanField(default=False, db_index=True)),
                ('complete', models.BooleanField(default=False, db_index=True)),
                ('log_file', models.TextField()),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('env', models.CharField(max_length=255)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Machine',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('hostname', models.CharField(max_length=255)),
                ('ip', models.CharField(max_length=255)),
                ('deploys', models.ManyToManyField(to='chief.Deploy')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Stage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('in_progress', models.BooleanField(default=True)),
                ('name', models.CharField(max_length=255)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=False, db_index=True)),
                ('deploy', models.ForeignKey(to='chief.Deploy')),
                ('machine', models.ForeignKey(to='chief.Machine')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
