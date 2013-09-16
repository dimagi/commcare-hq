from casexml.apps.case.models import CommCareCaseGroup
from corehq import CaseReassignmentInterface
from corehq.apps.data_interfaces.forms import AddCaseGroupForm
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin, FetchCRUDPaginatedDataView
from corehq.apps.reports.standard.export import ExcelExportReport
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop


@login_and_domain_required
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()

    if request.couch_user.can_view_reports():
        return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                            args=[domain, ExcelExportReport.slug]))
    exportable_reports = request.couch_user.get_exportable_reports(domain)
    if exportable_reports:
        return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                            args=[domain, exportable_reports[0]]))
    if request.couch_user.can_edit_data():
        return HttpResponseRedirect(reverse(EditDataInterfaceDispatcher.name(),
                                            args=[domain, CaseReassignmentInterface.slug]))
    raise Http404()


class CaseGroupListView(BaseDomainView, CRUDPaginatedViewMixin):
    template_name = "data_interfaces/list_case_groups.html"
    urlname = 'case_group_list'
    page_title = ugettext_noop("Case Groups")
    section_name = ugettext_noop("Data")

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def total(self):
        return CommCareCaseGroup.get_total(self.domain)

    @property
    def crud_url(self):
        return reverse(CRUDCaseGroupListView.urlname, args=[self.domain])

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return AddCaseGroupForm(self.request.POST)
        return AddCaseGroupForm()

    @property
    def column_names(self):
        return [
            _("Group Name"),
            _("Number of Cases"),
            _("Action"),
        ]

    @property
    def page_context(self):
        return self.pagination_context


class CRUDCaseGroupListView(FetchCRUDPaginatedDataView, CaseGroupListView):
    urlname = 'fetch_case_group_list'


