from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule


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
        migrations.AddIndex(
            model_name='alertschedule',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='alertschedule_deleted_on_idx'),
        ),
        migrations.AddIndex(
            model_name='timedschedule',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='timedschedule_deleted_on_idx'),
        ),
        migrations.RunPython(set_deleted_on_field)
    ]
