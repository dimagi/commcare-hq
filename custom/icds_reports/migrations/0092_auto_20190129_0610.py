# Generated by Django 1.11.17 on 2019-01-29 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0091_lunch'),
    ]

    operations = [
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='conceive',
            field=models.PositiveSmallIntegerField(help_text="Has ever had /data/conceive = 'yes'", null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='counsel_accessible_ppfp',
            field=models.PositiveSmallIntegerField(help_text="Has ever had /data/family_planning_group/counsel_accessible_ppfp='yes'", null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='counsel_preparation',
            field=models.PositiveSmallIntegerField(help_text="Has ever had /data/bp2/counsel_preparation = 'yes'", null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='ifa_last_seven_days',
            field=models.PositiveSmallIntegerField(help_text='Number of ifa taken in last seven days', null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='play_birth_preparedness_vid',
            field=models.PositiveSmallIntegerField(help_text='Case has ever been counseled about birth preparedness with a video', null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='play_family_planning_vid',
            field=models.PositiveSmallIntegerField(help_text='Case has ever been counseled about family planning with a video', null=True),
        ),
        migrations.AddField(
            model_name='aggregatebirthpreparednesforms',
            name='using_ifa',
            field=models.PositiveSmallIntegerField(help_text="Has ever had /data/bp1/using_ifa='yes'", null=True),
        ),
        migrations.AddField(
            model_name='aggregateccsrecorddeliveryforms',
            name='where_born',
            field=models.PositiveSmallIntegerField(help_text='Where the child is born', null=True),
        ),
        migrations.AlterField(
            model_name='aggls',
            name='awc_visits',
            field=models.IntegerField(help_text='awc visits made by LS'),
        ),
        migrations.AlterField(
            model_name='aggregatelsawcvisitform',
            name='awc_visits',
            field=models.IntegerField(help_text='awc visits made by LS'),
        ),
    ]
