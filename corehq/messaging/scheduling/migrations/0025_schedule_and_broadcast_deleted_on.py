from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    TimedSchedule,
)


def set_deleted_on_field(apps, schema_editor):
    migrate_to_deleted_on(AlertSchedule, 'deleted')
    migrate_to_deleted_on(TimedSchedule, 'deleted')
    migrate_to_deleted_on(ScheduledBroadcast, 'deleted')
    migrate_to_deleted_on(ImmediateBroadcast, 'deleted')


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
            model_name='immediatebroadcast',
            name='deleted_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='scheduledbroadcast',
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
                fields=['deleted_on'], name='scheduling_alerts_a959504b_idx'),
        ),
        migrations.AddIndex(
            model_name='immediatebroadcast',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='scheduling_immedi_bdf4439b_idx'),
        ),
        migrations.AddIndex(
            model_name='scheduledbroadcast',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='scheduling_schedu_be9e6e8c_idx'),
        ),
        migrations.AddIndex(
            model_name='timedschedule',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='scheduling_timeds_7faa3256_idx'),
        ),
        migrations.RunPython(set_deleted_on_field),
    ]
