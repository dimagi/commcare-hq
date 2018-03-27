# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-03-17 06:45
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations, models
from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0035_auto_20180317_0645'),
    ]

    operations = [
        migrator.get_migration('update_tables18.sql'),
        migrations.CreateModel(
            name='ChildHealthMonthly',
            fields=[
                ('awc_id', models.TextField()),
                ('case_id', models.TextField(primary_key=True)),
                ('month', models.DateField()),
                ('age_in_months', models.IntegerField(blank=True, null=True)),
                ('open_in_month', models.IntegerField(blank=True, null=True)),
                ('alive_in_month', models.IntegerField(blank=True, null=True)),
                ('wer_eligible', models.IntegerField(blank=True, null=True)),
                ('nutrition_status_last_recorded', models.TextField(blank=True, null=True)),
                ('current_month_nutrition_status', models.TextField(blank=True, null=True)),
                ('nutrition_status_weighed', models.IntegerField(blank=True, null=True)),
                ('num_rations_distributed', models.IntegerField(blank=True, null=True)),
                ('pse_eligible', models.IntegerField(blank=True, null=True)),
                ('pse_days_attended', models.IntegerField(blank=True, null=True)),
                ('born_in_month', models.IntegerField(blank=True, null=True)),
                ('low_birth_weight_born_in_month', models.IntegerField(blank=True, null=True)),
                ('bf_at_birth_born_in_month', models.IntegerField(blank=True, null=True)),
                ('ebf_eligible', models.IntegerField(blank=True, null=True)),
                ('ebf_in_month', models.IntegerField(blank=True, null=True)),
                ('ebf_not_breastfeeding_reason', models.TextField(blank=True, null=True)),
                ('ebf_drinking_liquid', models.IntegerField(blank=True, null=True)),
                ('ebf_eating', models.IntegerField(blank=True, null=True)),
                ('ebf_no_bf_no_milk', models.IntegerField(blank=True, null=True)),
                ('ebf_no_bf_pregnant_again', models.IntegerField(blank=True, null=True)),
                ('ebf_no_bf_child_too_old', models.IntegerField(blank=True, null=True)),
                ('ebf_no_bf_mother_sick', models.IntegerField(blank=True, null=True)),
                ('cf_eligible', models.IntegerField(blank=True, null=True)),
                ('cf_in_month', models.IntegerField(blank=True, null=True)),
                ('cf_diet_diversity', models.IntegerField(blank=True, null=True)),
                ('cf_diet_quantity', models.IntegerField(blank=True, null=True)),
                ('cf_handwashing', models.IntegerField(blank=True, null=True)),
                ('cf_demo', models.IntegerField(blank=True, null=True)),
                ('fully_immunized_eligible', models.IntegerField(blank=True, null=True)),
                ('fully_immunized_on_time', models.IntegerField(blank=True, null=True)),
                ('fully_immunized_late', models.IntegerField(blank=True, null=True)),
                ('counsel_ebf', models.IntegerField(blank=True, null=True)),
                ('counsel_adequate_bf', models.IntegerField(blank=True, null=True)),
                ('counsel_pediatric_ifa', models.IntegerField(blank=True, null=True)),
                ('counsel_comp_feeding_vid', models.IntegerField(blank=True, null=True)),
                ('counsel_increase_food_bf', models.IntegerField(blank=True, null=True)),
                ('counsel_manage_breast_problems', models.IntegerField(blank=True, null=True)),
                ('counsel_skin_to_skin', models.IntegerField(blank=True, null=True)),
                ('counsel_immediate_breastfeeding', models.IntegerField(blank=True, null=True)),
                ('recorded_weight', models.DecimalField(
                    max_digits=65535, decimal_places=65535, blank=True, null=True
                )),
                ('recorded_height', models.DecimalField(
                    max_digits=65535, decimal_places=65535, blank=True, null=True
                )),
                ('has_aadhar_id', models.IntegerField(blank=True, null=True)),
                ('thr_eligible', models.IntegerField(blank=True, null=True)),
                ('pnc_eligible', models.IntegerField(blank=True, null=True)),
                ('cf_initiation_in_month', models.IntegerField(blank=True, null=True)),
                ('cf_initiation_eligible', models.IntegerField(blank=True, null=True)),
                ('height_measured_in_month', models.IntegerField(blank=True, null=True)),
                ('current_month_stunting', models.TextField(blank=True, null=True)),
                ('stunting_last_recorded', models.TextField(blank=True, null=True)),
                ('wasting_last_recorded', models.TextField(blank=True, null=True)),
                ('current_month_wasting', models.TextField(blank=True, null=True)),
                ('valid_in_month', models.IntegerField(blank=True, null=True)),
                ('valid_all_registered_in_month', models.IntegerField(blank=True, null=True)),
                ('ebf_no_info_recorded', models.IntegerField(blank=True, null=True)),
                ('dob', models.DateField(blank=True, null=True)),
                ('sex', models.TextField(blank=True, null=True)),
                ('age_tranche', models.TextField(blank=True, null=True)),
                ('caste', models.TextField(blank=True, null=True)),
                ('disabled', models.TextField(blank=True, null=True)),
                ('minority', models.TextField(blank=True, null=True)),
                ('resident', models.TextField(blank=True, null=True)),
                ('person_name', models.TextField(blank=True, null=True)),
                ('current_month_nutrition_status_sort', models.IntegerField(blank=True, null=True)),
                ('current_month_stunting_sort', models.IntegerField(blank=True, null=True)),
                ('current_month_wasting_sort', models.IntegerField(blank=True, null=True)),
                ('mother_name', models.TextField(blank=True, null=True)),
                ('fully_immunized', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'child_health_monthly',
                'managed': False,
            }
        ),
        migrations.CreateModel(
            name='UcrTableNameMapping',
            fields=[
                ('table_type', models.TextField(primary_key=True)),
                ('table_name', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'ucr_table_name_mapping',
                'managed': False,
            }
        )
    ]
