from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from corehq.apps.app_execution import const
from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.data_model import EXAMPLE_WORKFLOW
from corehq.apps.app_execution.db_accessors import get_avg_duration_data
from corehq.apps.app_execution.exceptions import AppExecutionError, FormplayerException
from corehq.apps.app_execution.forms import AppWorkflowConfigForm
from corehq.apps.app_execution.har_parser import parse_har_from_string
from corehq.apps.app_execution.models import AppExecutionLog, AppWorkflowConfig
from corehq.apps.domain.decorators import require_superuser_or_contractor
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@require_superuser_or_contractor
@use_bootstrap5
def workflow_list(request, domain):
    workflows = AppWorkflowConfig.objects.filter(domain=domain)
    _augment_with_logs(workflows)
    utcnow = datetime.utcnow()
    chart_data = get_avg_duration_data(domain, start=utcnow - relativedelta(months=1), end=utcnow)
    context = _get_context(
        request,
        "Automatically Executed App Workflows",
        reverse("app_execution:workflow_list", args=[domain]),
        workflows=workflows,
        chart_data=chart_data
    )
    return render(request, "app_execution/workflow_list.html", context)


def _augment_with_logs(workflows):
    """Add log records to each workflow object. Always at 10 even if there are less than 10 logs.
    """
    for workflow in workflows:
        log_status = [{}] * 10
        logs = AppExecutionLog.objects.filter(workflow=workflow).order_by("-started")[:10]
        for i, log in enumerate(logs):
            log_status[9 - i] = {"success": log.success, "id": log.id}
        workflow.last_n = log_status


@require_superuser_or_contractor
@use_bootstrap5
def delete_workflow(request, domain, pk):
    workflow = get_object_or_404(AppWorkflowConfig, domain=domain, pk=pk)
    workflow.delete()
    return redirect("app_execution:workflow_list", domain)


@require_superuser_or_contractor
@use_bootstrap5
def new_workflow(request, domain):
    form = AppWorkflowConfigForm(request, initial={
        "workflow": EXAMPLE_WORKFLOW, "run_every": 1, "form_mode": const.FORM_MODE_HUMAN
    })
    if request.method == "POST":
        import_har = request.POST.get("import_har")
        har_file = request.FILES.get("har_file")
        if import_har and har_file:
            form = _get_form_from_har(har_file.read(), request)
        else:
            form = AppWorkflowConfigForm(request, request.POST)
            if form.is_valid():
                form.save()
                return redirect("app_execution:workflow_list", domain)

    context = _get_context(
        request, "New App Workflow", reverse("app_execution:new_workflow", args=[domain]),
        add_parent=True, form=form
    )
    return render(request, "app_execution/workflow_form.html", context)


@require_superuser_or_contractor
@use_bootstrap5
def edit_workflow(request, domain, pk):
    config = get_object_or_404(AppWorkflowConfig, domain=domain, pk=pk)
    form = AppWorkflowConfigForm(request, instance=config)
    if request.method == "POST":
        form = AppWorkflowConfigForm(request, request.POST, instance=config)
        import_har = request.POST.get("import_har")
        har_file = request.FILES.get("har_file")
        if import_har and har_file:
            form = _get_form_from_har(har_file.read(), request, instance=config)
        elif har_file:
            messages.error(request, "You must use the 'Import HAR' button to upload a HAR file.")
        else:
            if form.is_valid():
                form.save()
                return redirect("app_execution:workflow_list", domain)

    context = _get_context(
        request, f"Edit App Workflow: {config.name}", reverse("app_execution:edit_workflow", args=[domain, pk]),
        add_parent=True, form=form
    )
    return render(request, "app_execution/workflow_form.html", context)


def _get_form_from_har(har_data_string, request, instance=None):
    post_data = request.POST.copy()
    try:
        config = parse_har_from_string(har_data_string)
        post_data["domain"] = config.domain
        post_data["app_id"] = config.app_id
        post_data["workflow"] = AppWorkflowConfig.workflow_object_to_json_string(config.workflow)
    except Exception as e:
        messages.error(request, "Unable to process HAR file: " + str(e))

    return AppWorkflowConfigForm(request, post_data, instance=instance)


@require_superuser_or_contractor
@use_bootstrap5
def test_workflow(request, domain, pk):
    config = get_object_or_404(AppWorkflowConfig, domain=domain, pk=pk)

    context = _get_context(
        request, f"Test App Workflow: {config.name}", reverse("app_execution:test_workflow", args=[domain, pk]),
        add_parent=True, workflow=config
    )

    if request.method == "POST":
        session = config.get_formplayer_session()
        try:
            execute_workflow(session, config.workflow)
        except (AppExecutionError, FormplayerException) as e:
            context["error"] = str(e)
            context["success"] = False
        else:
            context["success"] = True

        context["result"] = True
        context["output"] = session.get_logs()
        context["workflow_json"] = config.workflow_json

    return render(request, "app_execution/workflow_test.html", context)


def _get_context(request, title, url, add_parent=False, **kwargs):
    parents = [{
        "title": "App Testing",
        "url": reverse("app_execution:workflow_list", args=[request.domain]),
    }]
    context = {
        "domain": request.domain,
        "current_page": {
            "page_name": title,
            "title": title,
            "url": url,
            "parents": parents if add_parent else [],
        },
        "section": {"page_name": "Apps", "url": "#"},
    }
    return {**context, **kwargs}


@require_superuser_or_contractor
@use_bootstrap5
def workflow_log_list(request, domain, pk):
    utcnow = datetime.utcnow()
    chart_data = get_avg_duration_data(
        domain, start=utcnow - relativedelta(months=1), end=utcnow, workflow_id=pk
    )
    context = _get_context(
        request,
        "Automatically Executed App Workflow Logs",
        reverse("app_execution:workflow_logs", args=[domain, pk]),
        add_parent=True,
        workflow=AppWorkflowConfig.objects.get(id=pk),
        total=AppExecutionLog.objects.filter(workflow__domain=domain, workflow_id=pk).count(),
        chart_data=chart_data
    )
    return render(request, "app_execution/workflow_log_list.html", context)


@require_superuser_or_contractor
@use_bootstrap5
def workflow_logs_json(request, domain, pk):
    limit = int(request.GET.get('per_page', 10))
    page = int(request.GET.get('page', 1))
    skip = limit * (page - 1)
    logs = AppExecutionLog.objects.filter(
        workflow__domain=domain, workflow_id=pk
    ).order_by("-started")[skip:skip + limit]
    return JsonResponse({
        "logs": [
            {
                "id": log.id,
                "started": log.started.strftime("%Y-%m-%d %H:%M:%SZ"),
                "completed": log.completed.strftime("%Y-%m-%d %H:%M:%SZ") if log.completed else None,
                "success": log.success,
                "duration": str(log.duration) if log.duration else "",
                "url": reverse("app_execution:workflow_log", args=[domain, log.id])
            }
            for log in logs
        ]
    })


@require_superuser_or_contractor
@use_bootstrap5
def workflow_log(request, domain, pk):
    log = get_object_or_404(AppExecutionLog, workflow__domain=domain, pk=pk)
    return render(
        request, "app_execution/workflow_log.html",
        _get_context(
            request,
            f"Workflow Log: {log.workflow.name}",
            reverse("app_execution:workflow_log", args=[domain, pk]),
            add_parent=True,
            log=log,
            workflow_json=log.workflow.workflow_json
        )
    )
