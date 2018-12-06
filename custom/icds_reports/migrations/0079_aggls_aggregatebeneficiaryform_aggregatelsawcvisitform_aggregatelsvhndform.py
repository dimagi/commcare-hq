# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-27 21:26
from __future__ import unicode_literals
from __future__ import absolute_import

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0078_add_phone_number_to_child_health_monthly'),
    ]

    operations = [
        migrations.CreateModel(
            name='AggLs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unique_awc_vists', models.IntegerField(help_text='unique awc visits made by LS')),
                ('vhnd_observed', models.IntegerField(help_text='VHND forms submitted by LS')),
                ('beneficiary_vists', models.IntegerField(help_text='Beneficiary visits done by LS')),
                ('month', models.DateField()),
                ('state_id', models.TextField()),
                ('district_id', models.TextField()),
                ('block_id', models.TextField()),
                ('supervisor_id', models.TextField()),
                ('aggregation_level', models.SmallIntegerField()),
            ],
            options={
                'db_table': 'agg_ls',
            },
        ),
        migrations.CreateModel(
            name='AggregateBeneficiaryForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('beneficiary_vists', models.IntegerField(help_text='Beneficiary visits done by LS')),
                ('month', models.DateField()),
                ('supervisor_id', models.TextField()),
                ('state_id', models.TextField()),
            ],
            options={
                'db_table': 'icds_dashboard_ls_beneficiary_forms',
            },
        ),
        migrations.CreateModel(
            name='AggregateLsAWCVisitForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unique_awc_vists', models.IntegerField(help_text='unique awc visits made by LS')),
                ('month', models.DateField()),
                ('supervisor_id', models.TextField()),
                ('state_id', models.TextField()),
            ],
            options={
                'db_table': 'icds_dashboard_ls_awc_visits_forms',
            },
        ),
        migrations.CreateModel(
            name='AggregateLsVhndForm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vhnd_observed', models.IntegerField(help_text='VHND forms submitted by LS')),
                ('month', models.DateField()),
                ('supervisor_id', models.TextField()),
                ('state_id', models.TextField()),
            ],
            options={
                'db_table': 'icds_dashboard_ls_vhnd_forms',
            },
        ),
    ]
