# Generated by Django 1.10.6 on 2017-04-04 12:54

import django.db.models.deletion
from django.db import migrations, models

import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0005_remove_match_type_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseRuleAction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='CaseRuleCriteria',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='ClosedParentDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(default='parent', max_length=126)),
                ('relationship_id', models.PositiveSmallIntegerField(default=1)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CustomActionDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=126)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CustomMatchDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=126)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MatchPropertyDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('property_name', models.CharField(max_length=126)),
                ('property_value', models.CharField(max_length=126, null=True)),
                ('match_type', models.CharField(max_length=15)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='UpdateCaseDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('properties_to_update', jsonfield.fields.JSONField(default=list)),
                ('close_case', models.BooleanField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='automaticupdaterule',
            name='migrated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='caserulecriteria',
            name='closed_parent_definition',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.ClosedParentDefinition'),
        ),
        migrations.AddField(
            model_name='caserulecriteria',
            name='custom_match_definition',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.CustomMatchDefinition'),
        ),
        migrations.AddField(
            model_name='caserulecriteria',
            name='match_property_definition',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.MatchPropertyDefinition'),
        ),
        migrations.AddField(
            model_name='caserulecriteria',
            name='rule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='data_interfaces.AutomaticUpdateRule'),
        ),
        migrations.AddField(
            model_name='caseruleaction',
            name='custom_action_definition',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.CustomActionDefinition'),
        ),
        migrations.AddField(
            model_name='caseruleaction',
            name='rule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='data_interfaces.AutomaticUpdateRule'),
        ),
        migrations.AddField(
            model_name='caseruleaction',
            name='update_case_definition',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.UpdateCaseDefinition'),
        ),
    ]
