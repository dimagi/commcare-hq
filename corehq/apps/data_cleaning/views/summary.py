from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class ChangesSummaryView(BulkEditSessionViewMixin,
                         LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = "bulk_edit_changes_summary"
    session_not_found_message = gettext_lazy("Cannot retrieve summary, session was not found.")

    def get(self, request, *args, **kwargs):
        # this view can only be POSTed to and accessed at specific hq_hx_action endpoints
        raise Http404()

    @hq_hx_action('post')
    def undo_changes_summary(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "data_cleaning/summary/undo_changes.html",
            {
                "change": self.session.changes.last(),
            },
        )

    @hq_hx_action('post')
    def clear_changes_summary(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "data_cleaning/summary/clear_changes.html",
            {
                "changes": self.session.changes.all(),
                "num_changes": self.session.changes.count(),
            },
        )

    @hq_hx_action('post')
    def apply_changes_summary(self, request, *args, **kwargs):
        return self.render_htmx_partial_response(
            request,
            "data_cleaning/summary/apply_changes.html",
            {
                "changes": self.session.changes.all(),
                "num_changes": self.session.changes.count(),
            },
        )
