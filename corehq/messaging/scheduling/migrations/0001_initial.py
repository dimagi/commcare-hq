# Generated by Django 1.9.12 on 2017-03-10 01:10

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AlertEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('time_to_wait', models.TimeField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AlertSchedule',
            fields=[
                ('schedule_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('active', models.BooleanField(default=True)),
                ('include_descendant_locations', models.BooleanField(default=False)),
                ('default_language_code', models.CharField(max_length=126, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EmailContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', jsonfield.fields.JSONField(default=dict)),
                ('message', jsonfield.fields.JSONField(default=dict)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ImmediateBroadcast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('name', models.CharField(max_length=1000)),
                ('last_sent_timestamp', models.DateTimeField(null=True)),
                ('schedule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduling.AlertSchedule')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IVRSurveyContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('form_unique_id', models.CharField(max_length=126)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScheduledBroadcast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('name', models.CharField(max_length=1000)),
                ('last_sent_timestamp', models.DateTimeField(null=True)),
                ('start_date', models.DateField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SMSContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', jsonfield.fields.JSONField(default=dict)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SMSSurveyContent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('form_unique_id', models.CharField(max_length=126)),
                ('expire_after', models.IntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TimedEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('day', models.IntegerField()),
                ('time', models.TimeField()),
                ('email_content', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.EmailContent')),
                ('ivr_survey_content', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.IVRSurveyContent')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TimedSchedule',
            fields=[
                ('schedule_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('active', models.BooleanField(default=True)),
                ('include_descendant_locations', models.BooleanField(default=False)),
                ('default_language_code', models.CharField(max_length=126, null=True)),
                ('schedule_length', models.IntegerField()),
                ('total_iterations', models.IntegerField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='timedevent',
            name='schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduling.TimedSchedule'),
        ),
        migrations.AddField(
            model_name='timedevent',
            name='sms_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.SMSContent'),
        ),
        migrations.AddField(
            model_name='timedevent',
            name='sms_survey_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.SMSSurveyContent'),
        ),
        migrations.AddField(
            model_name='scheduledbroadcast',
            name='schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduling.TimedSchedule'),
        ),
        migrations.AddField(
            model_name='alertevent',
            name='email_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.EmailContent'),
        ),
        migrations.AddField(
            model_name='alertevent',
            name='ivr_survey_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.IVRSurveyContent'),
        ),
        migrations.AddField(
            model_name='alertevent',
            name='schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scheduling.AlertSchedule'),
        ),
        migrations.AddField(
            model_name='alertevent',
            name='sms_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.SMSContent'),
        ),
        migrations.AddField(
            model_name='alertevent',
            name='sms_survey_content',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.SMSSurveyContent'),
        ),
    ]
