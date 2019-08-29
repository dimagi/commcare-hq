# flake8: noqa
# Generated by Django 1.11.20 on 2019-02-25 18:22

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aaa', '0004_auto_20190222_1955_squashed_0005_woman_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChildHistory',
            fields=[
                ('child_health_case_id', models.TextField(primary_key=True, serialize=False)),
                ('weight_child_history', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=2), null=True, size=None)),
                ('height_child_history', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=2), null=True, size=None)),
                ('zscore_grading_wfa_history', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=2), null=True, size=None)),
                ('zscore_grading_hfa_history', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=2), null=True, size=None)),
                ('zscore_grading_wfh_history', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), size=2), null=True, size=None)),
            ],
        ),
        migrations.AddField(
            model_name='ccsrecord',
            name='lmp',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='birth_weight',
            field=models.PositiveIntegerField(help_text='birth weight in grams', null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='breastfed_within_first',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='ccs_record_case_id',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='child_cried',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='comp_feeding',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='contact_phone_number',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='diet_diversity',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='diet_quantity',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='hand_wash',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='has_aadhar_number',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='child',
            name='hh_address',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='hh_bpl_apl',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='hh_caste',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='hh_religion',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='is_exclusive_breastfeeding',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='name',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='child',
            name='tasks_case_id',
            field=models.TextField(null=True),
        ),
    ]
