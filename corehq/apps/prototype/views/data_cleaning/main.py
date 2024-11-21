from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.prototype.models.data_cleaning.cache_store import (
    FakeCaseDataStore,
    SlowSimulatorStore,
    VisibleColumnStore,
    FilterColumnStore,
    ShowWhitespacesStore,
    FakeCaseDataHistoryStore,
)
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.htmx_debug import HqHtmxDebugMixin


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class CaseDataCleaningPrototypeView(HqHtmxDebugMixin, HqHtmxActionMixin, BasePageView):
    urlname = "prototype_data_cleaning_case"
    template_name = 'prototype/data_cleaning/case_prototype.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            "case_type": "mother",
            "show_whitespaces": ShowWhitespacesStore(self.request).get(),
        }

    @hq_hx_action('post')
    def toggle_whitespace(self, request, *args, **kwargs):
        space_store = ShowWhitespacesStore(request)
        if 'show_whitespaces' in request.POST:
            space_store.set(True)
        else:
            space_store.delete()
        return self.render_htmx_no_response(request, *args, **kwargs)


@require_superuser
def reset_data(request):
    stores = [
        VisibleColumnStore,
        FakeCaseDataStore,
        FilterColumnStore,
        ShowWhitespacesStore,
        FakeCaseDataHistoryStore,
    ]
    applied_to_user = None
    for store_class in stores:
        data_store = store_class(request)
        username = request.GET.get('username')
        if username:
            data_store.username = username
        applied_to_user = data_store.username
        data_store.delete()
    return JsonResponse({
        "cleared": True,
        "username": applied_to_user,
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
