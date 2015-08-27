# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField()),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('create_date', models.DateTimeField(editable=False)),
                ('update_date', models.DateTimeField(editable=False)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
                ('type', models.CharField(max_length=50, null=True, blank=True)),
                ('number', models.PositiveIntegerField(default=0)),
                ('text', models.TextField()),
                ('url', models.CharField(max_length=100, null=True, blank=True)),
                ('expires', models.DateTimeField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeliveryGroupReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('quantity', models.IntegerField()),
                ('report_date', models.DateTimeField(default=datetime.datetime(2015, 7, 31, 17, 38, 49, 821416))),
                ('message', models.CharField(max_length=100, db_index=True)),
                ('delivery_group', models.CharField(max_length=1)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
            ],
            options={
                'ordering': ('-report_date',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='GroupSummary',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=50, null=True, blank=True)),
                ('total', models.PositiveIntegerField(default=0)),
                ('responded', models.PositiveIntegerField(default=0)),
                ('on_time', models.PositiveIntegerField(default=0)),
                ('complete', models.PositiveIntegerField(default=0)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HistoricalLocationGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateField()),
                ('group', models.CharField(max_length=1)),
                ('location_id', models.ForeignKey(to='locations.SQLLocation')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ILSNotes',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=100)),
                ('user_name', models.CharField(max_length=128)),
                ('user_role', models.CharField(max_length=100, null=True)),
                ('user_phone', models.CharField(max_length=20, null=True)),
                ('date', models.DateTimeField()),
                ('text', models.TextField()),
                ('location', models.ForeignKey(to='locations.SQLLocation')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OrganizationSummary',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField()),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('create_date', models.DateTimeField(editable=False)),
                ('update_date', models.DateTimeField(editable=False)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
                ('total_orgs', models.PositiveIntegerField(default=0)),
                ('average_lead_time_in_days', models.FloatField(default=0)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProductAvailabilityData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField()),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('create_date', models.DateTimeField(editable=False)),
                ('update_date', models.DateTimeField(editable=False)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
                ('product', models.CharField(max_length=100, db_index=True)),
                ('total', models.PositiveIntegerField(default=0)),
                ('with_stock', models.PositiveIntegerField(default=0)),
                ('without_stock', models.PositiveIntegerField(default=0)),
                ('without_data', models.PositiveIntegerField(default=0)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ReportRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('start_run', models.DateTimeField()),
                ('end_run', models.DateTimeField(null=True)),
                ('complete', models.BooleanField(default=False)),
                ('has_error', models.BooleanField(default=False)),
                ('domain', models.CharField(max_length=60)),
                ('location', models.ForeignKey(to='locations.SQLLocation', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RequisitionReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('submitted', models.BooleanField(default=False)),
                ('report_date', models.DateTimeField(default=datetime.datetime.utcnow)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SupervisionDocument',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('document', models.TextField()),
                ('domain', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=100)),
                ('data_type', models.CharField(max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SupplyPointStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status_type', models.CharField(max_length=50, choices=[(b'rr_fac', b'rr_fac'), (b'soh_fac', b'soh_fac'), (b'super_fac', b'super_fac'), (b'rr_dist', b'rr_dist'), (b'del_del', b'del_del'), (b'la_fac', b'la_fac'), (b'del_dist', b'del_dist'), (b'del_fac', b'del_fac')])),
                ('status_value', models.CharField(max_length=50, choices=[(b'received', b'received'), (b'not_received', b'not_received'), (b'submitted', b'submitted'), (b'not_submitted', b'not_submitted'), (b'reminder_sent', b'reminder_sent'), (b'alert_sent', b'alert_sent')])),
                ('status_date', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('location_id', models.CharField(max_length=100, db_index=True)),
                ('external_id', models.PositiveIntegerField(null=True, db_index=True)),
            ],
            options={
                'ordering': ('-status_date',),
                'get_latest_by': 'status_date',
                'verbose_name': 'Facility Status',
                'verbose_name_plural': 'Facility Statuses',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SupplyPointWarehouseRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('supply_point', models.CharField(max_length=100, db_index=True)),
                ('create_date', models.DateTimeField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='historicallocationgroup',
            unique_together=set([('location_id', 'date', 'group')]),
        ),
        migrations.AddField(
            model_name='groupsummary',
            name='org_summary',
            field=models.ForeignKey(to='ilsgateway.OrganizationSummary'),
            preserve_default=True,
        ),
    ]
