import json

from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import TemplateView
from memoized import memoized

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
    template_previous_session = "data_cleaning/status/previous_session.html"

    @property
    def seconds_since_complete(self):
        if self.session.completed_on is None:
            return 0
        delta = timezone.now() - self.session.completed_on
        return int(delta.total_seconds())

    @property
    def is_session_in_progress(self):
        return self.session.committed_on is not None and self.seconds_since_complete < APPLY_CHANGES_WAIT_TIME

    @property
    def weighted_percent_complete(self):
        """
        Returns an integer between 0 and 100.

        While the session is in progress we “pad” the percentage so
        the UI doesn't jump backward when the change feed catches up.

        TODO: update this buffer (APPLY_CHANGES_WAIT_TIME) dynamically based on change feed status.
        """
        base = self.session.percent_complete or 0
        if not self.is_session_in_progress:
            return base

        buffer = float(self.seconds_since_complete) / APPLY_CHANGES_WAIT_TIME
        weighted_percent = int(0.9 * base + 10 * buffer)
        return min(weighted_percent, 100)

    def get_template_names(self):
        if self.is_session_in_progress:
            return [self.template_in_progress]
        elif self.active_session:
            return [self.template_previous_session]
        return [self.template_name]

    @property
    @memoized
    def active_session(self):
        if self.session.completed_on is None:
            return None
        return BulkEditSession.objects.active_case_session(
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
            "num_records_changed": (
                self.session.num_changed_records
                if self.session.committed_on is not None
                else 0
            ),
            "case_type": self.session.identifier,
            "exit_url": self.exit_url,
            "is_task_complete": self.session.percent_complete == 100,
            "weighted_percent_complete": self.weighted_percent_complete,
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
        return self.include_gtm_event_with_response(
            response,
            "bulk_edit_session_status_viewed",
            {
                "session_type": self.session.session_type,
                "commit_in_progress": self.is_session_in_progress,
                "has_active_session": self.active_session is not None,
            }
        )

    @hq_hx_action('get')
    def poll_session_status(self, request, *args, **kwargs):
        # we call super() to avoid triggering "showDataCleaningModal" again
        return super().get(request, *args, **kwargs)

    @hq_hx_action('post')
    def resume_session(self, request, *args, **kwargs):
        if self.active_session is not None:
            self.active_session.delete()
        new_session = self.session.get_resumed_session()

        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView
        new_session_url = reverse(
            BulkEditCasesSessionView.urlname,
            args=(self.domain, new_session.session_id),
        )
        query_string = request.META.get('QUERY_STRING', '')
        return self.render_htmx_redirect(
            f"{new_session_url}?{query_string}",
            response_message=_("Resuming Bulk Edit Session..."),
        )
