from __future__ import absolute_import
from django.http import HttpResponse
from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView

from dimagi.utils.couch.cache.cache_core import get_redis_client
from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required, require_superuser
from corehq.form_processor.exceptions import CaseNotFound
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

    @method_decorator(require_superuser)
    def get(self, request, *args, **kwargs):
        return super(ReconciliationTaskView, self).get(request, *args, **kwargs)

    @staticmethod
    def permitted_tasks():
        return [choice[0] for choice in ReconciliationTaskForm().fields['task'].choices]

    def get_context_data(self, **kwargs):
        kwargs['reconciliation_form'] = ReconciliationTaskForm()
        return super(ReconciliationTaskView, self).get_context_data(**kwargs)

    @staticmethod
    def parse_person_case_ids(person_case_ids, domain):
        """
        ensure case ids are open person cases
        :param person_case_ids: comma separated case id
        :return: parsed case ids or return None in case unable to
        """
        person_case_ids = person_case_ids.split(',')
        case_accessor = CaseAccessors(domain)
        try:
            person_cases = case_accessor.get_cases(person_case_ids)
        except CaseNotFound:
            return None
        parsed_person_case_ids = []
        for person_case in person_cases:
            if not person_case or person_case.type != 'person' or person_case.closed:
                return None
            else:
                parsed_person_case_ids.append(person_case.case_id)
        return parsed_person_case_ids

    @method_decorator(require_superuser)
    def post(self, request, *args, **kwargs):
        def run_task(task_name):
            run_model_reconciliation.delay(
                task_name,
                request.POST.get('email'),
                person_case_ids,
                (request.POST.get('commit') == 'on'),
            )
        task_requested = request.POST.get('task')
        person_case_ids = None
        if request.POST.get('person_case_ids'):
            person_case_ids = self.parse_person_case_ids(request.POST.get('person_case_ids'), request.domain)
            if not person_case_ids:
                return JsonResponse({'message': 'Please check person ids. They should be open person cases'})
        if task_requested == 'all':
            for task_to_run in ReconciliationTaskForm.permitted_tasks:
                run_task(task_to_run)
        elif task_requested in ReconciliationTaskForm.permitted_tasks:
            run_task(task_requested)
        return JsonResponse({'message': 'Task queued. You would get an email shortly.'})
