from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, DateTimeField, DurationField, ExpressionWrapper, F, Max
from django.db.models.functions import Trunc

from corehq.apps.app_execution.models import AppExecutionLog, AppWorkflowConfig


def get_avg_duration_data(domain, start, end, workflow_id=None):
    query = AppExecutionLog.objects.filter(workflow__domain=domain, started__gte=start, started__lt=end)
    if workflow_id:
        query = query.filter(workflow_id=workflow_id)

    chart_logs = (
        query.annotate(
            date=Trunc("started", "hour", output_field=DateTimeField()),
            duration=ExpressionWrapper(F("completed") - F("started"), output_field=DurationField()),
        ).values("date", "workflow_id")
        .annotate(avg_duration=Avg('duration'))
        .annotate(max_duration=Max('duration'))
    )

    data = defaultdict(list)
    seen_dates = defaultdict(set)
    for row in chart_logs:
        data[row["workflow_id"]].append({
            "date": row["date"].isoformat(),
            "avg_duration": row["avg_duration"].total_seconds(),
            "max_duration": row["max_duration"].total_seconds(),
        })
        seen_dates[row["workflow_id"]].add(row["date"])

    start = start.replace(minute=0, second=0, microsecond=0)
    current = start
    while current < end:
        for workflow_id, dates in seen_dates.items():
            if current not in dates:
                data[workflow_id].append({"date": current.isoformat(), "avg_duration": None, "max_duration": None})
        current += timedelta(hours=1)

    workflow_names = {
        workflow["id"]: workflow["name"]
        for workflow in AppWorkflowConfig.objects.filter(id__in=list(data)).values("id", "name")
    }
    return [
        {
            "key": workflow_id,
            "label": workflow_names[workflow_id],
            "values": sorted(data, key=lambda x: x["date"])
        }
        for workflow_id, data in data.items()
    ]


def get_status_data(domain, start, end, workflow_id=None):
    query = AppExecutionLog.objects.filter(workflow__domain=domain, started__gte=start, started__lt=end)
    if workflow_id:
        query = query.filter(workflow_id=workflow_id)

    chart_logs = (
        query.annotate(date=Trunc("started", "hour", output_field=DateTimeField()))
        .values("date", "success")
        .annotate(count=Count("success"))
    )

    success = []
    error = []
    seen_success_dates = set()
    seen_error_dates = set()
    for row in chart_logs:
        item = {
            "date": row["date"].isoformat(),
            "count": row["count"],
        }
        if row["success"]:
            success.append(item)
            seen_success_dates.add(row["date"])
        else:
            error.append(item)
            seen_error_dates.add(row["date"])

    start = start.replace(minute=0, second=0, microsecond=0)
    current = start
    while current < end:
        if current not in seen_error_dates:
            error.append({"date": current.isoformat(), "count": 0})
        if current not in seen_success_dates:
            success.append({"date": current.isoformat(), "count": 0})
        current += timedelta(hours=1)

    return [
        {"key": "Success", "values": sorted(success, key=lambda x: x["date"])},
        {"key": "Error", "values": sorted(error, key=lambda x: x["date"])},
    ]
