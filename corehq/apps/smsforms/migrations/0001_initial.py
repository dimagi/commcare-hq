from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SQLXFormsSession',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=50, db_index=True)),
                ('connection_id', models.CharField(db_index=True, max_length=50, null=True, blank=True)),
                ('session_id', models.CharField(db_index=True, max_length=50, null=True, blank=True)),
                ('form_xmlns', models.CharField(max_length=100, null=True, blank=True)),
                ('start_time', models.DateTimeField()),
                ('modified_time', models.DateTimeField()),
                ('end_time', models.DateTimeField(null=True)),
                ('completed', models.BooleanField(default=False)),
                ('domain', models.CharField(db_index=True, max_length=100, null=True, blank=True)),
                ('user_id', models.CharField(max_length=50, null=True, blank=True)),
                ('app_id', models.CharField(max_length=50, null=True, blank=True)),
                ('submission_id', models.CharField(max_length=50, null=True, blank=True)),
                ('survey_incentive', models.CharField(max_length=100, null=True, blank=True)),
                ('session_type', models.CharField(default='SMS', max_length=10, choices=[('SMS', 'SMS'), ('IVR', 'IVR')])),
                ('workflow', models.CharField(max_length=20, null=True, blank=True)),
                ('reminder_id', models.CharField(max_length=50, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
