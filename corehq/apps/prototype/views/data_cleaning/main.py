from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.decorators import (
    use_bootstrap5,
    use_alpinejs,
    use_htmx,
)
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.prototype.models.data_cleaning.cache_store import (
    FakeCaseDataStore,
    SlowSimulatorStore,
)


@method_decorator(use_htmx, name='dispatch')
@method_decorator(use_alpinejs, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class CaseDataCleaningPrototypeView(BasePageView):
    urlname = "prototype_data_cleaning_case"
    template_name = 'prototype/data_cleaning/case_prototype.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            "case_type": "child",
        }


@require_superuser
def reset_data(request):
    data_store = FakeCaseDataStore(request)
    username = request.GET.get('username')
    if username:
        data_store.username = username
    data_store.delete()
    return JsonResponse({
        "cleared": True,
        "username": data_store.username,
    })


@require_superuser
def slow_simulator(request):
    slow_store = SlowSimulatorStore(request)
    username = request.GET.get('username')
    slow_sate = request.GET.get('slow_state')
    if username:
        slow_store.username = username
    if slow_sate:
        slow_store.set(int(slow_sate))
    else:
        slow_store.delete()
    return JsonResponse({
        "updated": True,
        "slow_state": slow_sate,
        "username": slow_store.username,
    })
