from django.db.models import Avg, DateTimeField, DurationField, ExpressionWrapper, F, Max
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
        .order_by("workflow_id", "date")
    )

    data = []
    seen_workflows = set()
    for row in chart_logs:
        if row["workflow_id"] not in seen_workflows:
            seen_workflows.add(row["workflow_id"])
            data.append({
                "key": row["workflow_id"],
                "values": []
            })
        data[-1]["values"].append({
            "date": row["date"].isoformat(),
            "avg_duration": row["avg_duration"].total_seconds(),
            "max_duration": row["max_duration"].total_seconds(),
        })

    workflow_names = {
        workflow["id"]: workflow["name"]
        for workflow in AppWorkflowConfig.objects.filter(id__in=seen_workflows).values("id", "name")
    }
    for workflow_data in data:
        workflow_data["label"] = workflow_names[workflow_data["key"]]
    return data
