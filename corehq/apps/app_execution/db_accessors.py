from django.db.models import Avg, DateTimeField, DurationField, ExpressionWrapper, F, Max
from django.db.models.functions import Trunc

from corehq.apps.app_execution.models import AppExecutionLog


def get_avg_duration_data(workflow_id, start, end):
    chart_logs = (
        AppExecutionLog.objects.filter(workflow_id=workflow_id)
        .filter(started__gte=start, started__lt=end)
        .annotate(
            date=Trunc("started", "hour", output_field=DateTimeField()),
            duration=ExpressionWrapper(F("completed") - F("started"), output_field=DurationField()),
        ).values("date")
        .annotate(avg_duration=Avg('duration'))
        .annotate(max_duration=Max('duration'))
        .order_by("date")
    )
    return [
        {
            "date": row["date"].isoformat(),
            "avg_duration": row["avg_duration"].total_seconds(),
            "max_duration": row["max_duration"].total_seconds(),
        }
        for row in chart_logs
    ]
