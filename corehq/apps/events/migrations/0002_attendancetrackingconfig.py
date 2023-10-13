from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_add_events_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceTrackingConfig',
            fields=[
                ('domain', models.CharField(
                    max_length=255,
                    primary_key=True,
                    serialize=False,
                )),
                ('mobile_worker_attendees', models.BooleanField(default=False)),
                ('attendee_case_type', models.CharField(
                    default='commcare-attendee',
                    max_length=255,
                )),
            ],
        ),
    ]
