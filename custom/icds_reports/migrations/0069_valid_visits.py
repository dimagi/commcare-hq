# Generated by Django 1.11.16 on 2018-10-04 21:18

from django.db import migrations, models

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0068_ccsrecordmonthlyview_add_lactating')
    ]

    operations = [
        migrations.CreateModel(
            name='AggregateCcsRecordComplementaryFeedingForms',
            fields=[
                ('state_id', models.CharField(max_length=40)),
                ('month', models.DateField(help_text='Will always be YYYY-MM-01')),
                ('case_id', models.CharField(max_length=40, primary_key=True, serialize=False)),
                ('latest_time_end_processed', models.DateTimeField(help_text='The latest form.meta.timeEnd that has been processed for this case')),
                ('valid_visits', models.PositiveSmallIntegerField(default=0, help_text='number of qualified visits for the incentive report')),
            ],
            options={
                'db_table': 'icds_dashboard_ccs_record_cf_forms',
            },
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='valid_visits',
            field=models.PositiveSmallIntegerField(default=0, help_text='number of qualified visits for the incentive report'),
        ),
        migrations.AddField(
            model_name='aggregateccsrecorddeliveryforms',
            name='valid_visits',
            field=models.PositiveSmallIntegerField(default=0, help_text='number of qualified visits for the incentive report'),
        ),
        migrations.AddField(
            model_name='aggregateccsrecordpostnatalcareforms',
            name='valid_visits',
            field=models.PositiveSmallIntegerField(default=0, help_text='number of qualified visits for the incentive report'),
        ),
        migrations.CreateModel(
            name='AWWIncentiveReport',
            fields=[
                ('state_id', models.CharField(max_length=40)),
                ('month', models.DateField(help_text='Will always be YYYY-MM-01')),
                ('awc_id', models.CharField(max_length=40, primary_key=True, serialize=False)),
                ('block_id', models.CharField(max_length=40)),
                ('state_name', models.TextField(null=True)),
                ('district_name', models.TextField(null=True)),
                ('block_name', models.TextField(null=True)),
                ('supervisor_name', models.TextField(null=True)),
                ('awc_name', models.TextField(null=True)),
                ('aww_name', models.TextField(null=True)),
                ('contact_phone_number', models.TextField(null=True)),
                ('wer_weighed', models.SmallIntegerField(null=True)),
                ('wer_eligible', models.SmallIntegerField(null=True)),
                ('awc_num_open', models.SmallIntegerField(null=True)),
                ('valid_visits', models.SmallIntegerField(null=True)),
                ('expected_visits', models.SmallIntegerField(null=True)),
            ],
            options={
                'db_table': 'icds_dashboard_aww_incentive',
            },
        ),
        migrator.get_migration('update_tables29.sql')
    ]
