from django.conf import settings

from corehq.celery_monitoring.heartbeat import Heartbeat


# Create one periodic_task named heartbeat__{queue} for each queue
for queue, time_to_start_alert_threshold in settings.CELERY_HEARTBEAT_THRESHOLDS.items():
    heartbeat = Heartbeat(queue)
    locals()[heartbeat.periodic_task_name] = heartbeat.make_periodic_task()
