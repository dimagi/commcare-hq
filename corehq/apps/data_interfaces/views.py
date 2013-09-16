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
    if request.project.commtrack_enabled:
        if not request.couch_user.is_domain_admin():
            raise Http404()
        from corehq.apps.commtrack.views import ProductListView
        return HttpResponseRedirect(reverse(ProductListView.urlname,
                                            args=[domain]))
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
        return len(CommCareCaseGroup.get_all(self.domain))

    @property
    def crud_url(self):
        return reverse(CRUDCaseGroupListView.urlname, args=[self.domain])

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return AddCaseGroupForm(self.request.POST)
        return AddCaseGroupForm()

    def get_new_item_data(self, create_form):
        return {
            'itemData': {
                'id': 'ewreawr121342',
                'name': 'All New Group',
                'numCases': 2,
            },
            'templateSelector': '#new-group-row',

    def get_updated_item_data(self, item_id):
        # todo delete the case group here
        return {
            'itemData': {
                'id': '313235dsfa',
                'name': 'New Group (Deleted)',
                'numCases': 0,
            },
            'template': 'modified-group-template',
        }

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

    @property
    def paginated_list(self):
        return [
            {
                'itemData': {
                    'id': '313235dsfa',
                    'name': 'New Group',
                    'numCases': 0,
                },
                'templateSelector': '#existing-group-row',
            }
        ]


