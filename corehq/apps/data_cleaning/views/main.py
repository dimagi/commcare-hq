from django.contrib import messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET
from memoized import memoized

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.models import BulkEditSession
from corehq.apps.data_cleaning.utils.cases import clear_caches_case_data_cleaning
from corehq.apps.data_cleaning.views.bulk_edit import EditSelectedRecordsFormView
from corehq.apps.data_cleaning.views.columns import ManageColumnsFormView
from corehq.apps.data_cleaning.views.filters import ManageFiltersView, ManagePinnedFiltersView
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.data_cleaning.views.start import StartCaseSessionView
from corehq.apps.data_cleaning.views.status import BulkEditSessionStatusView
from corehq.apps.data_cleaning.views.tables import EditCasesTableView, RecentCaseSessionsTableView
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util.view_utils import set_file_download


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class BulkEditCasesMainView(BaseProjectDataView):
    page_title = gettext_lazy("Bulk Edit Case Data")
    urlname = "bulk_edit_cases_main"
    template_name = "data_cleaning/bulk_edit_main.html"

    @property
    def page_context(self):
        return {
            "htmx_start_session_form_view_url": reverse(
                StartCaseSessionView.urlname,
                args=(self.domain,),
            ),
            "htmx_recent_sessions_table_view_url": reverse(
                RecentCaseSessionsTableView.urlname,
                args=(self.domain,),
            ),
        }


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class BulkEditCasesSessionView(BulkEditSessionViewMixin, BaseProjectDataView):
    """
    This view is a "host" view of several HTMX views that handle
    different parts of the Bulk Editing feature.
    """
    page_title = gettext_lazy("Bulk Edit Case Type")
    urlname = "bulk_edit_cases_session"
    template_name = "data_cleaning/bulk_edit_session.html"
    redirect_on_missing_session = True

    def get_redirect_url(self):
        return reverse(BulkEditCasesMainView.urlname, args=(self.domain, ))

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
            'title': BulkEditCasesMainView.page_title,
            'url': reverse(BulkEditCasesMainView.urlname, args=(self.domain,)),
        }]

    @property
    def page_context(self):
        return {
            "htmx_primary_view_url": reverse(
                EditCasesTableView.urlname,
                args=(self.domain, self.session_id),
            ),
            "htmx_pinned_filters_view_url": reverse(
                ManagePinnedFiltersView.urlname,
                args=(self.domain, self.session_id),
            ),
            "htmx_filters_view_url": reverse(
                ManageFiltersView.urlname,
                args=(self.domain, self.session_id),
            ),
            "htmx_columns_view_url": reverse(
                ManageColumnsFormView.urlname,
                args=(self.domain, self.session_id),
            ),
            "htmx_edit_selected_records_view_url": reverse(
                EditSelectedRecordsFormView.urlname,
                args=(self.domain, self.session_id),
            ),
            "htmx_session_status_view_url": reverse(
                BulkEditSessionStatusView.urlname,
                args=(self.domain, self.session_id),
            ),
        }


@require_bulk_data_cleaning_cases
@login_and_domain_required
def clear_session_caches(request, domain, session_id):
    session = BulkEditSession.objects.get(session_id=session_id)
    clear_caches_case_data_cleaning(session.domain, session.identifier)
    messages.success(request, _("Caches successfully cleared."))
    return redirect(reverse(BulkEditCasesMainView.urlname, args=(domain,)))


@require_GET
@require_bulk_data_cleaning_cases
@login_and_domain_required
def download_form_ids(request, domain, session_id):
    session = BulkEditSession.objects.get(session_id=session_id)

    ids_stream = ('{}\n'.format(form_id) for form_id in session.form_ids)
    response = StreamingHttpResponse(ids_stream, content_type='text/plain')
    set_file_download(response, f"{domain}-data_cleaning-form_ids.txt")

    return response
