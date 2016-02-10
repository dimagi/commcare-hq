# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
        ('sms', '0010_update_sqlmobilebackend_couch_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsBillable',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('gateway_fee_conversion_rate', models.DecimalField(default=Decimal('1.0'), null=True, max_digits=20, decimal_places=9)),
                ('log_id', models.CharField(max_length=50, db_index=True)),
                ('phone_number', models.CharField(max_length=50)),
                ('api_response', models.TextField(null=True, blank=True)),
                ('is_valid', models.BooleanField(default=True, db_index=True)),
                ('domain', models.CharField(max_length=25, db_index=True)),
                ('direction', models.CharField(db_index=True, max_length=10, choices=[(b'I', b'Incoming'), (b'O', b'Outgoing')])),
                ('date_sent', models.DateField()),
                ('date_created', models.DateField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SmsGatewayFee',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('amount', models.DecimalField(default=0.0, max_digits=10, decimal_places=4)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SmsGatewayFeeCriteria',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('backend_api_id', models.CharField(max_length=100, db_index=True)),
                ('backend_instance', models.CharField(max_length=255, null=True, db_index=True)),
                ('direction', models.CharField(db_index=True, max_length=10, choices=[(b'I', b'Incoming'), (b'O', b'Outgoing')])),
                ('country_code', models.IntegerField(db_index=True, max_length=5, null=True, blank=True)),
                ('prefix', models.CharField(default=b'', max_length=10, db_index=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SmsUsageFee',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('amount', models.DecimalField(default=0.0, max_digits=10, decimal_places=4)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SmsUsageFeeCriteria',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('direction', models.CharField(db_index=True, max_length=10, choices=[(b'I', b'Incoming'), (b'O', b'Outgoing')])),
                ('domain', models.CharField(max_length=25, null=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='smsusagefee',
            name='criteria',
            field=models.ForeignKey(to='smsbillables.SmsUsageFeeCriteria', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='smsgatewayfee',
            name='criteria',
            field=models.ForeignKey(to='smsbillables.SmsGatewayFeeCriteria', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='smsgatewayfee',
            name='currency',
            field=models.ForeignKey(to='accounting.Currency', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='smsbillable',
            name='gateway_fee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='smsbillables.SmsGatewayFee', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='smsbillable',
            name='usage_fee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='smsbillables.SmsUsageFee', null=True),
            preserve_default=True,
        ),
    ]
