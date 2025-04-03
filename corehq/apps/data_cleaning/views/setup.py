from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.setup import (
    SelectCaseTypeForm,
    ResumeOrRestartCaseSessionForm,
)
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class SetupCaseSessionFormView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = "data_cleaning_select_case_type_form"
    template_name = "data_cleaning/forms/next_action_form.html"
    container_id = "setup-case-session"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "form": kwargs.pop('form', None) or SelectCaseTypeForm(self.domain),
            "container_id": self.container_id,
            "next_action": kwargs.pop('next_action', 'validate_session'),
        })
        return context

    @hq_hx_action('post')
    def validate_session(self, request, *args, **kwargs):
        form = SelectCaseTypeForm(self.domain, request.POST)
        next_action = 'validate_session'
        if form.is_valid():
            case_type = form.cleaned_data['case_type']
            active_session = BulkEditSession.get_active_case_session(
                request.user, self.domain, case_type
            )
            if not active_session:
                new_session = BulkEditSession.new_case_session(
                    request.user, self.domain, case_type
                )
                return self.render_session_redirect(new_session)
            form = ResumeOrRestartCaseSessionForm(
                self.domain, self.container_id, request.path_info, {
                    'case_type': case_type,
                    'next_step': 'resume',
                },
            )
            next_action = 'resume_or_restart'
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    @hq_hx_action('post')
    def resume_or_restart(self, request, *args, **kwargs):
        form = ResumeOrRestartCaseSessionForm(
            self.domain, self.container_id, request.path_info, request.POST
        )
        next_action = 'resume_or_restart'
        if form.is_valid():
            case_type = form.cleaned_data['case_type']
            next_step = form.cleaned_data['next_step']
            get_session = {
                'resume': lambda: BulkEditSession.get_active_case_session(
                    request.user, self.domain, case_type
                ),
                'new': lambda: BulkEditSession.restart_case_session(
                    request.user, self.domain, case_type
                ),
            }[next_step]
            if get_session:
                return self.render_session_redirect(get_session())
        return self.get(request, form=form, next_action=next_action, *args, **kwargs)

    def render_session_redirect(self, session):
        from corehq.apps.data_cleaning.views.main import CleanCasesSessionView
        response = HttpResponse(_("Starting Data Cleaning Session..."))
        response['HX-Redirect'] = reverse(
            CleanCasesSessionView.urlname, args=(self.domain, session.session_id, )
        )
        return response
