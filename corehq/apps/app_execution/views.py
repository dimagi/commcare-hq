from django.shortcuts import get_object_or_404, redirect, render

from corehq.apps.app_execution.api import execute_workflow
from corehq.apps.app_execution.exceptions import AppExecutionError
from corehq.apps.app_execution.forms import AppWorkflowConfigForm
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.domain.decorators import require_superuser_or_contractor
from corehq.apps.hqadmin.views import get_hqadmin_base_context
from corehq.apps.hqwebapp.decorators import use_bootstrap5


@require_superuser_or_contractor
@use_bootstrap5
def workflow_list(request):
    context = get_hqadmin_base_context(request)
    context["workflows"] = AppWorkflowConfig.objects.all()
    return render(request, "app_execution/workflow_list.html", context)


@require_superuser_or_contractor
@use_bootstrap5
def new_workflow(request):
    form = AppWorkflowConfigForm()
    if request.method == "POST":
        form = AppWorkflowConfigForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("app_execution:workflow_list")

    context = get_hqadmin_base_context(request)
    context["form"] = form
    return render(request, "app_execution/workflow_form.html", context)


@require_superuser_or_contractor
@use_bootstrap5
def edit_workflow(request, pk):
    config = get_object_or_404(AppWorkflowConfig, pk=pk)
    form = AppWorkflowConfigForm(instance=config)
    if request.method == "POST":
        form = AppWorkflowConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            return redirect("app_execution:workflow_list")

    context = get_hqadmin_base_context(request)
    context["form"] = form
    return render(request, "app_execution/workflow_form.html", context)


@require_superuser_or_contractor
@use_bootstrap5
def test_workflow(request, pk):
    config = get_object_or_404(AppWorkflowConfig, pk=pk)
    context = get_hqadmin_base_context(request)
    context["workflow"] = config

    if request.method == "POST":
        session = config.get_formplayer_session()
        try:
            execute_workflow(session, config.workflow)
        except AppExecutionError as e:
            context["error"] = str(e)

        context["result"] = True
        context["log"] = session.log.getvalue()

    return render(request, "app_execution/workflow_test.html", context)
