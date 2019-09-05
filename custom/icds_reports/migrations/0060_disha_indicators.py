# Generated by Django 1.11.14 on 2018-08-20 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0059_update_blob_paths'),
    ]

    operations = [
        migrations.CreateModel(
            name='DishaIndicatorView',
            fields=[
                ('awc_id', models.TextField(primary_key=True)),
                ('awc_name', models.TextField(blank=True, null=True)),
                ('supervisor_id', models.TextField(blank=True, null=True)),
                ('supervisor_name', models.TextField(blank=True, null=True)),
                ('block_id', models.TextField(blank=True, null=True)),
                ('block_name', models.TextField(blank=True, null=True)),
                ('district_id', models.TextField(blank=True, null=True)),
                ('district_name', models.TextField(blank=True, null=True)),
                ('state_id', models.TextField(blank=True, null=True)),
                ('state_name', models.TextField(blank=True, null=True)),
                ('aggregation_level', models.IntegerField(blank=True, null=True)),
                ('month', models.DateField(blank=True, null=True)),
                ('cases_household', models.IntegerField(blank=True, null=True)),
                ('cases_person_all', models.IntegerField(blank=True, null=True)),
                ('cases_person', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_pregnant_all', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_pregnant', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_lactating_all', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_lactating', models.IntegerField(blank=True, null=True)),
                ('cases_child_health_all', models.IntegerField(blank=True, null=True)),
                ('cases_child_health', models.IntegerField(blank=True, null=True)),
                ('medicine_kit_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('infant_weighing_scale_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('adult_weighing_scale_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('clean_water_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('functional_toilet_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('anemic_pregnant_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('tetanus_complete_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('anc1_received_at_delivery_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('anc2_received_at_delivery_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('anc3_received_at_delivery_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('anc4_received_at_delivery_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('resting_during_pregnancy_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('extra_meal_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('counsel_immediate_bf_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('nutrition_status_weighed_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('height_measured_in_month_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('nutrition_status_unweighed', models.IntegerField(blank=True, null=True)),
                ('nutrition_status_severely_underweight_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('nutrition_status_moderately_underweight_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('wasting_severe_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('wasting_moderate_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('stunting_severe_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('stunting_moderate_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('low_birth_weight_in_month_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
                ('immunized_percent', models.DecimalField(max_digits=16, decimal_places=8, blank=True, null=True)),
            ],
            options={
                'db_table': 'icds_disha_indicators',
                'managed': False,
            }
        )
    ]
