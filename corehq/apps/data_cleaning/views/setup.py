import uuid

from django.http import HttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from corehq import toggles
from corehq.apps.data_cleaning.forms.setup import SelectCaseTypeForm
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class SetupCaseSessionFormView(HqHtmxActionMixin, LoginAndDomainMixin, DomainViewMixin, TemplateView):
    urlname = "data_cleaning_select_case_type_form"
    template_name = "data_cleaning/partials/forms/next_action_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "form": kwargs.pop('form', SelectCaseTypeForm(self.domain)),
            "container_id": "setup-case-session",
            "next_action": kwargs.pop('next_action', 'validate_session'),
        })
        return context

    @hq_hx_action('post')
    def validate_session(self, request, *args, **kwargs):
        form = SelectCaseTypeForm(self.domain, request.POST)
        if form.is_valid():
            return self.render_session_redirect()
        return self.get(request, form=form, *args, **kwargs)

    def render_session_redirect(self):
        from corehq.apps.data_cleaning.views.main import CleanCasesSessionView
        fake_session_id = uuid.uuid4()
        response = HttpResponse(_("Starting Data Cleaning Session..."))
        response['HX-Redirect'] = reverse(
            CleanCasesSessionView.urlname, args=(self.domain, fake_session_id, )
        )
        return response
