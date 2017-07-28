from django.http import HttpResponse
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import View

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from .exceptions import EnikshayTaskException
from .tasks import EpisodeAdherenceUpdate


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
