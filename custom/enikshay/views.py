from celery.task.base import Task
from django.http import HttpResponse
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View, TemplateView

from dimagi.utils.couch.cache.cache_core import get_redis_client
from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from .exceptions import EnikshayTaskException
from .tasks import EpisodeAdherenceUpdate, CACHE_KEY


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
        except EnikshayTaskException, e:
            return HttpResponse(e)


class EpisodeTaskStatusView(TemplateView):
    urlname = 'episode_task_status'
    template_name = 'enikshay/episode_updater_debug.html'

    @method_decorator(domain_admin_required)
    def get(self, request, domain, *args, **kwargs):
        cache = get_redis_client()
        task_id = cache.get(CACHE_KEY)
        task = Task.AsyncResult(task_id)
        return self.render_to_response({
            "task_id": task,
            "success_pct": 100 * task.info['success'] / task.info['total'] if task.info else 0,
            "fail_pct": 100 * task.info['fail'] / task.info['total'] if task.info else 0,
            "success": task.info['success'] if task.info else 0,
            "fail": task.info['fail'] if task.info else 0,
            "total": task.info['total'] if task.info else 0,
            "errors": task.info['errors'] if task.info else [],
            "batches": task.info['batches'] if task.info else [],
            "time": task.info['time_elapsed'] if task.info else [],
        })
