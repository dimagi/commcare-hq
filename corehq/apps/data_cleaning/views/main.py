from memoized import memoized

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy, gettext as _

from corehq import toggles
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class CleanCasesMainView(BaseProjectDataView):
    page_title = gettext_lazy("Clean Case Data")
    urlname = "data_cleaning_cases"
    template_name = "data_cleaning/clean_cases_main.html"

    @property
    def page_context(self):
        from corehq.apps.data_cleaning.views.setup import SetupCaseSessionFormView
        from corehq.apps.data_cleaning.views.tables import CaseCleaningTasksTableView
        return {
            "setup_case_session_form_url": reverse(SetupCaseSessionFormView.urlname, args=(self.domain,)),
            "tasks_table_url": reverse(CaseCleaningTasksTableView.urlname, args=(self.domain, )),
        }


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class CleanCasesSessionView(BaseProjectDataView):
    page_title = gettext_lazy("Clean Case Type")
    urlname = "data_cleaning_cases_session"
    template_name = "data_cleaning/clean_cases_session.html"

    def get(self, request, *args, **kwargs):
        try:
            return super(CleanCasesSessionView, self).get(request, *args, **kwargs)
        except BulkEditSession.DoesNotExist:
            messages.error(request, _("That session does not exist. Please start a new session."))
            return redirect(reverse(CleanCasesMainView.urlname, args=(self.domain, )))

    @property
    def session_id(self):
        return self.kwargs['session_id']

    @property
    @memoized
    def session(self):
        return BulkEditSession.objects.get(session_id=self.session_id)

    @property
    def case_type(self):
        return self.session.identifier

    @property
    def page_name(self):
        return _('Case Type "{case_type}"').format(case_type=self.case_type)

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=(self.domain, self.session_id,))

    @property
    def parent_pages(self):
        return [{
            'title': CleanCasesMainView.page_title,
            'url': reverse(CleanCasesMainView.urlname, args=(self.domain,)),
        }]

    @property
    def page_context(self):
        return {
            "session_id": self.session_id,
        }
