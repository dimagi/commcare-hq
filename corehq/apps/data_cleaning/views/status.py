import json

from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.utils import timezone
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.models.session import APPLY_CHANGES_WAIT_TIME, BulkEditSession
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
    template_in_progress = "data_cleaning/status/in_progress.html"

    @property
    def seconds_since_complete(self):
        if self.session.completed_on is None:
            return 0
        delta = timezone.now() - self.session.completed_on
        return int(delta.total_seconds())

    @property
    def is_session_in_progress(self):
        return self.session.committed_on is not None and self.seconds_since_complete < APPLY_CHANGES_WAIT_TIME

    def get_template_names(self):
        if self.is_session_in_progress:
            return [self.template_in_progress]
        return [self.template_name]

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
            "num_records_changed": (
                self.session.num_changed_records
                if self.session.committed_on is not None
                else 0
            ),
            "case_type": self.session.identifier,
            "exit_url": self.exit_url,
            "is_task_complete": self.session.percent_complete == 100,
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

    @hq_hx_action('get')
    def poll_session_status(self, request, *args, **kwargs):
        # we call super() to avoid the default behavior of this view
        # which is to trigger the session status modal
        response = super().get(request, *args, **kwargs)
        if self.session.completed_on is not None:
            response['HX-Trigger'] = json.dumps({
                'statusRefresh': {
                    'target': '#primary-view-container',
                },
            })
        return response

    @hq_hx_action('post')
    def resume_session(self, request, *args, **kwargs):
        active_session = self.get_active_session()
        if active_session:
            active_session.delete()
        new_session = self.session.get_resumed_session()

        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView
        return self.render_htmx_redirect(
            reverse(
                BulkEditCasesSessionView.urlname,
                args=(self.domain, new_session.session_id),
            ),
            response_message=_("Resuming Bulk Edit Session..."),
        )
