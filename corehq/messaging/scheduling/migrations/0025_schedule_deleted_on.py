from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule

ALERT_INDEX_NAME = 'alertschedule_deleted_on_idx'
ALERT_TABLE_NAME = 'scheduling_alertschedule'
TIMED_INDEX_NAME = 'timedschedule_deleted_on_idx'
TIMED_TABLE_NAME = 'scheduling_timedschedule'
COLUMNS = 'deleted_on'
WHERE_CLAUSE = 'deleted_on IS NOT NULL'
ALERT_CREATE_INDEX = f"CREATE INDEX {ALERT_INDEX_NAME} ON {ALERT_TABLE_NAME} ({COLUMNS}) WHERE {WHERE_CLAUSE}"
TIMED_CREATE_INDEX = f"CREATE INDEX {TIMED_INDEX_NAME} ON {TIMED_TABLE_NAME} ({COLUMNS}) WHERE {WHERE_CLAUSE}"


def set_deleted_on_field(apps, schema_editor):
    migrate_to_deleted_on(AlertSchedule, 'deleted')
    migrate_to_deleted_on(TimedSchedule, 'deleted')


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0024_app_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertschedule',
            name='deleted_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='timedschedule',
            name='deleted_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunSQL(ALERT_CREATE_INDEX),
        migrations.RunSQL(TIMED_CREATE_INDEX),
        migrations.RunPython(set_deleted_on_field)
    ]
