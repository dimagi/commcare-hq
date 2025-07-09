from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.start_session import (
    ResumeOrRestartCaseSessionForm,
    SelectCaseTypeForm,
)
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(
    [
        use_bootstrap5,
        require_bulk_data_cleaning_cases,
    ],
    name='dispatch',
)
class StartCaseSessionView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = 'start_bulk_edit_case_session'
    template_name = 'hqwebapp/crispy/next_action_form.html'
    container_id = 'start-case-session'

    def get_context_data(self, form=None, next_action=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'form': form or SelectCaseTypeForm(self.domain),
                'container_id': self.container_id,
                'next_action': next_action or 'validate_session',
            }
        )
        return context

    @hq_hx_action('post')
    def validate_session(self, request, *args, **kwargs):
        form = SelectCaseTypeForm(self.domain, request.POST)
        next_action = 'validate_session'
        if form.is_valid():
            case_type = form.cleaned_data['case_type']
            active_session = BulkEditSession.objects.active_case_session(request.user, self.domain, case_type)
            if not active_session:
                new_session = BulkEditSession.objects.new_case_session(request.user, self.domain, case_type)
                return self.render_session_redirect(new_session, 'fresh')
            form = ResumeOrRestartCaseSessionForm(
                self.domain,
                self.container_id,
                request.path_info,
                {
                    'case_type': case_type,
                    'next_step': 'resume',
                },
            )
            next_action = 'resume_or_restart'
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    @hq_hx_action('post')
    def resume_or_restart(self, request, *args, **kwargs):
        form = ResumeOrRestartCaseSessionForm(self.domain, self.container_id, request.path_info, request.POST)
        next_action = 'resume_or_restart'
        if form.is_valid():
            case_type = form.cleaned_data['case_type']
            next_step = form.cleaned_data['next_step']
            get_session = {
                'resume': lambda: BulkEditSession.objects.active_case_session(
                    request.user, self.domain, case_type
                ),
                'new': lambda: BulkEditSession.objects.restart_case_session(request.user, self.domain, case_type),
            }[next_step]
            if get_session:
                return self.render_session_redirect(get_session(), next_step)
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    def render_session_redirect(self, session, creation_method):
        from corehq.apps.data_cleaning.views.main import BulkEditCasesSessionView

        response = self.render_htmx_redirect(
            reverse(
                BulkEditCasesSessionView.urlname,
                args=(
                    self.domain,
                    session.session_id,
                ),
            ),
            response_message=_('Starting Bulk Edit Session...'),
        )
        return self.include_gtm_event_with_response(
            response,
            'bulk_edit_session_started',
            {
                'creation_method': creation_method,
                'session_type': session.session_type,
            },
        )
