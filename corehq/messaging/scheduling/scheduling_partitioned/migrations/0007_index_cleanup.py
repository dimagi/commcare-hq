from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling_partitioned', '0006_unique_indexes'),
    ]

    operations = [
        # (case_id, alert_schedule_id) covered by unique(case_id, alert_schedule_id, recipient_type, recipient_id)
        migrations.AlterIndexTogether(
            name='casealertscheduleinstance',
            index_together=set([('domain', 'active', 'next_event_due'), ('active', 'next_event_due')]),
        ),
        # (case_id, timed_schedule_id) covered by unique(case_id, timed_schedule_id, recipient_type, recipient_id)
        migrations.AlterIndexTogether(
            name='casetimedscheduleinstance',
            index_together=set([('domain', 'active', 'next_event_due'), ('active', 'next_event_due')]),
        ),
    ]
