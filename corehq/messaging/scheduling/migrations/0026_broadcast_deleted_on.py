from django.db import migrations, models

from corehq.apps.cleanup.utils import migrate_to_deleted_on
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    ScheduledBroadcast,
)


def set_deleted_on_field(apps, schema_editor):
    migrate_to_deleted_on(ScheduledBroadcast, 'deleted')
    migrate_to_deleted_on(ImmediateBroadcast, 'deleted')


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0025_schedule_deleted_on'),
    ]

    operations = [
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
        migrations.AddIndex(
            model_name='immediatebroadcast',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='imm_broadcast_deleted_on_idx'),
        ),
        migrations.AddIndex(
            model_name='scheduledbroadcast',
            index=models.Index(
                condition=models.Q(('deleted_on__isnull', False)),
                fields=['deleted_on'], name='sch_broadcast_deleted_on_idx'),
        ),
        migrations.RunPython(set_deleted_on_field),
    ]
