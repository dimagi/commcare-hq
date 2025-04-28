from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class ChangesSummaryView(BulkEditSessionViewMixin,
                         LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = "data_cleaning_changes_summary"
    session_not_found_message = gettext_lazy("Cannot retrieve summary, session was not found.")

    def get(self, request, *args, **kwargs):
        # this view can only be POSTed to and accessed at specific hq_hx_action endpoints
        raise Http404()
