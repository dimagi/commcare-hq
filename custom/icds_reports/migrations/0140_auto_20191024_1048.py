from django.db import migrations, models

from corehq.util.django_migrations import AlterFieldCreateIndexIfNotExists


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0139_update_thr_view'),
    ]

    operations = [
        AlterFieldCreateIndexIfNotExists(
            model_name='icdsauditentryrecord',
            name='time_of_use',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.CreateModel(
            name='NICIndicatorsView',
            fields=[
                ('state_id', models.TextField(primary_key=True, serialize=False)),
                ('state_name', models.TextField(blank=True, null=True)),
                ('state_site_code', models.TextField(blank=True, null=True)),
                ('month', models.DateField(blank=True, null=True)),
                ('cases_household', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_pregnant', models.IntegerField(blank=True, null=True)),
                ('cases_ccs_lactating', models.IntegerField(blank=True, null=True)),
                ('cases_child_health', models.IntegerField(blank=True, null=True)),
                ('num_launched_awcs', models.IntegerField(blank=True, null=True)),
                ('ebf_in_month', models.IntegerField(blank=True, null=True)),
                ('cf_initiation_in_month', models.IntegerField(blank=True, null=True)),
                ('bf_at_birth', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'nic_indicators',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TakeHomeRationMonthly',
            fields=[
                ('awc_id', models.TextField(primary_key=True, serialize=False)),
                ('awc_name', models.TextField(blank=True, null=True)),
                ('awc_site_code', models.TextField(blank=True, null=True)),
                ('supervisor_id', models.TextField(blank=True, null=True)),
                ('supervisor_name', models.TextField(blank=True, null=True)),
                ('supervisor_site_code', models.TextField(blank=True, null=True)),
                ('block_id', models.TextField(blank=True, null=True)),
                ('block_name', models.TextField(blank=True, null=True)),
                ('block_site_code', models.TextField(blank=True, null=True)),
                ('district_id', models.TextField(blank=True, null=True)),
                ('district_name', models.TextField(blank=True, null=True)),
                ('district_site_code', models.TextField(blank=True, null=True)),
                ('state_id', models.TextField(blank=True, null=True)),
                ('state_name', models.TextField(blank=True, null=True)),
                ('state_site_code', models.TextField(blank=True, null=True)),
                ('aggregation_level', models.IntegerField(blank=True, null=True)),
                ('block_map_location_name', models.TextField(blank=True, null=True)),
                ('district_map_location_name', models.TextField(blank=True, null=True)),
                ('state_map_location_name', models.TextField(blank=True, null=True)),
                ('aww_name', models.TextField(blank=True, null=True)),
                ('contact_phone_number', models.TextField(blank=True, null=True)),
                ('thr_distribution_image_count', models.IntegerField(null=True)),
                ('is_launched', models.TextField(null=True)),
                ('month', models.DateField(blank=True, null=True)),
                ('thr_given_21_days', models.IntegerField(null=True)),
                ('total_thr_candidates', models.IntegerField(null=True)),
            ],
            options={
                'db_table': 'thr_report_monthly',
                'managed': False,
            },
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='comp_feeding_ever',
            field=models.PositiveSmallIntegerField(
                help_text='Complementary feeding has ever occurred for this case', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='comp_feeding_latest',
            field=models.PositiveSmallIntegerField(
                help_text='Complementary feeding occurred for this case in the latest form', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='counselled_pediatric_ifa',
            field=models.PositiveSmallIntegerField(
                help_text='Once the child is over 1 year, has ever been counseled on pediatric IFA', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='demo_comp_feeding',
            field=models.PositiveSmallIntegerField(help_text='Demo of complementary feeding has ever occurred',
                                                   null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='diet_diversity',
            field=models.PositiveSmallIntegerField(
                help_text='Diet diversity occurred for this case in the latest form', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='diet_quantity',
            field=models.PositiveSmallIntegerField(
                help_text='Diet quantity occurred for this case in the latest form', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='hand_wash',
            field=models.PositiveSmallIntegerField(
                help_text='Hand washing occurred for this case in the latest form', null=True),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='latest_time_end_processed',
            field=models.DateTimeField(
                help_text='The latest form.meta.timeEnd that has been processed for this case'),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='month',
            field=models.DateField(help_text='Will always be YYYY-MM-01'),
        ),
        migrations.AlterField(
            model_name='aggregatecomplementaryfeedingforms',
            name='play_comp_feeding_vid',
            field=models.PositiveSmallIntegerField(
                help_text='Case has ever been counseled about complementary feeding with a video', null=True),
        ),
    ]
