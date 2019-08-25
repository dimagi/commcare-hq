# -*- coding: utf-8 -*-

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AutomaticUpdateRule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, db_index=True)),
                ('name', models.CharField(max_length=126)),
                ('case_type', models.CharField(max_length=126)),
                ('active', models.BooleanField(default=False)),
                ('deleted', models.BooleanField(default=False)),
                ('last_run', models.DateTimeField(null=True)),
                ('server_modified_boundary', models.IntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AutomaticUpdateAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=10, choices=[(b'UPDATE', b'UPDATE'), (b'CLOSE', b'CLOSE')])),
                ('property_name', models.CharField(max_length=126, null=True)),
                ('property_value', models.CharField(max_length=126, null=True)),
                ('rule', models.ForeignKey(to='data_interfaces.AutomaticUpdateRule', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AutomaticUpdateRuleCriteria',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('property_name', models.CharField(max_length=126)),
                ('property_value', models.CharField(max_length=126, null=True)),
                ('match_type', models.CharField(max_length=10, choices=[(b'DAYS', b'DAYS'), (b'EQUAL', b'EQUAL'), (b'NOT_EQUAL', b'NOT_EQUAL'), (b'EXISTS', b'EXISTS')])),
                ('rule', models.ForeignKey(to='data_interfaces.AutomaticUpdateRule', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
