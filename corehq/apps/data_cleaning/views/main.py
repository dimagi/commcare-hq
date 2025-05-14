from memoized import memoized

from django.contrib import messages
from django.shortcuts import redirect
from django.http import StreamingHttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET
from django.utils.translation import gettext_lazy, gettext as _

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.data_cleaning.utils.cases import clear_caches_case_data_cleaning
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.view_utils import set_file_download


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class CleanCasesMainView(BaseProjectDataView):
    page_title = gettext_lazy("Bulk Edit Case Data")
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
    require_bulk_data_cleaning_cases,
], name='dispatch')
class CleanCasesSessionView(BulkEditSessionViewMixin, BaseProjectDataView):
    page_title = gettext_lazy("Bulk Edit Case Type")
    urlname = "data_cleaning_cases_session"
    template_name = "data_cleaning/clean_cases_session.html"
    redirect_on_session_exceptions = True

    def get_redirect_url(self):
        return reverse(CleanCasesMainView.urlname, args=(self.domain, ))

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
        return {}


@require_bulk_data_cleaning_cases
@login_and_domain_required
def clear_session_caches(request, domain, session_id):
    session = BulkEditSession.objects.get(session_id=session_id)
    clear_caches_case_data_cleaning(session.domain, session.identifier)
    messages.success(request, _("Caches successfully cleared."))
    return redirect(reverse(CleanCasesMainView.urlname, args=(domain,)))


@require_GET
@require_bulk_data_cleaning_cases
@login_and_domain_required
def download_form_ids(request, domain, session_id):
    session = BulkEditSession.objects.get(session_id=session_id)

    ids_stream = ('{}\n'.format(form_id) for form_id in session.form_ids)
    response = StreamingHttpResponse(ids_stream, content_type='text/plain')
    set_file_download(response, f"{domain}-data_cleaning-form_ids.txt")

    return response
