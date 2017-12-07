from __future__ import absolute_import
from django.http import HttpResponse
from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView

from dimagi.utils.couch.cache.cache_core import get_redis_client
from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from soil import MultipleTaskDownload

from .exceptions import EnikshayTaskException
from .tasks import EpisodeAdherenceUpdate, CACHE_KEY

from custom.enikshay.tasks import run_model_reconciliation
from custom.enikshay.forms import ReconciliationTaskForm


class EpisodeTaskDebugView(View):
    urlname = 'episode_task_debug'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.UATBC_ADHERENCE_TASK.required_decorator())
    def dispatch(self, *args, **kwargs):
        return super(EpisodeTaskDebugView, self).dispatch(*args, **kwargs)

    def get(self, request, domain, episode_id, *args, **kwargs):
        try:
            episode = CaseAccessors(domain).get_case(episode_id)
            return JsonResponse(EpisodeAdherenceUpdate(domain, episode).update_json())
        except EnikshayTaskException as e:
            return HttpResponse(e)


class EpisodeTaskStatusView(TemplateView):
    urlname = 'episode_task_status'

    @method_decorator(domain_admin_required)
    def get(self, request, domain, *args, **kwargs):
        cache = get_redis_client()
        download_id = cache.get(CACHE_KEY.format(domain))
        download = MultipleTaskDownload.get(download_id)
        if download:
            return redirect('hq_soil_download', domain, download.download_id)
        else:
            return HttpResponse(
                "Task with id: {} not found. Maybe it failed, never started, or completed a long time ago"
                .format(download_id))


class ReconciliationTaskView(TemplateView):
    template_name = "enikshay/reconciliation_tasks.html"

    @method_decorator(domain_admin_required)
    def get(self, request, *args, **kwargs):
        return super(ReconciliationTaskView, self).get(request, *args, **kwargs)

    @staticmethod
    def permitted_tasks():
        return [choice[0] for choice in ReconciliationTaskForm().fields['task'].choices]

    def get_context_data(self, **kwargs):
        kwargs['reconciliation_form'] = ReconciliationTaskForm()
        return super(ReconciliationTaskView, self).get_context_data(**kwargs)

    @method_decorator(domain_admin_required)
    def post(self, request, *args, **kwargs):
        def run_task(task_name):
            run_model_reconciliation.delay(
                task_name,
                request.POST.get('email'),
                (request.POST.get('commit') == 'on')
            )

        task_requested = request.POST.get('task')
        if task_requested == 'all':
            for task_to_run in ReconciliationTaskForm.permitted_tasks:
                run_task(task_to_run)
        elif task_requested in ReconciliationTaskForm.permitted_tasks:
            run_task(task_requested)
        return JsonResponse({'message': 'Task queued. You would get an email shortly.'})
