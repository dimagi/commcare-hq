import json

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.models.session import BulkEditSession
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class BaseStatusView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    pass


class BulkEditSessionStatusView(BulkEditSessionViewMixin, BaseStatusView):
    urlname = "bulk_edit_session_status"
    template_name = "data_cleaning/status/complete.html"

    def get_active_session(self):
        if self.session.completed_on is None:
            return None
        return BulkEditSession.get_active_case_session(
            self.request.user, self.domain, self.session.identifier
        )

    @property
    def exit_url(self):
        from corehq.apps.data_cleaning.views.main import BulkEditCasesMainView
        return reverse(
            BulkEditCasesMainView.urlname,
            args=(self.domain,),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_session": self.get_active_session(),
            "num_records_changed": self.session.num_changed_records,
            "case_type": self.session.identifier,
            "exit_url": self.exit_url,
        })
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if self.session.is_read_only:
            response['HX-Trigger'] = json.dumps({
                'showDataCleaningModal': {
                    'target': '#session-status-modal',
                },
            })
        return response

    @hq_hx_action('post')
    def resume_session(self, request, *args, **kwargs):

        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView
        return self.render_htmx_redirect(
            reverse(
                BulkEditCasesSessionView.urlname,
                args=(self.domain, self.session_id),
            ),
            response_message=_("Resuming Bulk Edit Session..."),
        )
