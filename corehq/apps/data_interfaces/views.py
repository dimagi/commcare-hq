from couchdbkit import ResourceNotFound
from django.utils.safestring import mark_safe
from casexml.apps.case.models import CommCareCaseGroup, CommCareCase
from corehq import CaseReassignmentInterface
from corehq.apps.data_interfaces.forms import AddCaseGroupForm, UpdateCaseGroupForm, AddCaseToGroup
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
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


class DataInterfaceSection(BaseDomainView):
    section_name = ugettext_noop("Data")

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])


class CaseGroupListView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = "data_interfaces/list_case_groups.html"
    urlname = 'case_group_list'
    page_title = ugettext_noop("Case Groups")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        return CommCareCaseGroup.get_total(self.domain)

    @property
    def column_names(self):
        return [
            _("Group Name"),
            _("Number of Cases"),
            _("Actions"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for group in CommCareCaseGroup.get_all(
                self.domain,
                limit=self.limit,
                skip=self.skip
            ):
            item_data = self._get_item_data(group)
            item_data['updateForm'] = self.get_update_form_response(
                self.get_update_form(initial_data={
                    'item_id': group._id,
                    'name': group.name,
                })
            )
            yield {
                'itemData': item_data,
                'template': 'existing-group-template',
            }

    def _get_item_data(self, case_group):
        return {
            'id': case_group._id,
            'name': case_group.name,
            'numCases': len(case_group.cases),
            'manageUrl': reverse(CaseGroupCaseManagementView.urlname, args=[self.domain, case_group._id])
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return AddCaseGroupForm(self.request.POST)
        return AddCaseGroupForm()

    def get_update_form(self, initial_data=None):
        if self.request.method == 'POST' and self.action == 'update':
            return UpdateCaseGroupForm(self.request.POST)
        return UpdateCaseGroupForm(initial=initial_data)

    def get_create_item_data(self, create_form):
        case_group = create_form.create_group(self.domain)
        return {
            'itemData': self._get_item_data(case_group),
            'template': 'new-group-template',
        }

    def get_updated_item_data(self, update_form):
        case_group = update_form.update_group()
        item_data = self._get_item_data(case_group)
        item_data['updateForm'] = self.get_update_form_response(update_form)
        return {
            'itemData': item_data,
            'template': 'existing-group-template',
        }

    def get_deleted_item_data(self, item_id):
        case_group = CommCareCaseGroup.get(item_id)
        item_data = self._get_item_data(case_group)
        case_group.delete()
        return {
            'itemData': item_data,
            'template': 'deleted-group-template',
        }


class CaseGroupCaseManagementView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = 'data_interfaces/manage_case_groups.html'
    urlname = 'manage_case_groups'
    page_title = ugettext_noop("Manage Group")

    @property
    def group_id(self):
        return self.kwargs.get('group_id')

    @property
    @memoized
    def case_group(self):
        try:
            return CommCareCaseGroup.get(self.group_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def parent_pages(self):
        return [{
            'title': CaseGroupListView.page_title,
            'url': reverse(CaseGroupListView.urlname, args=[self.domain])
        }]

    @property
    def page_name(self):
        return _("Manage Group '%s'" % self.case_group.name)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.group_id])

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def total(self):
        return len(self.case_group.cases)

    @property
    def column_names(self):
        return [
            _("Case Name"),
            _("Phone Number"),
            _("External ID"),
            _("Case Details"),
            _("Action"),
        ]

    @property
    def paginated_list(self):
        for case in self.case_group.get_cases(limit=self.limit, skip=self.skip):
            yield {
                'itemData': self._get_item_data(case),
                'template': 'existing-case-template',
            }

    def _get_item_data(self, case):
        return {
            'id': case._id,
            'detailsUrl': reverse('case_details', args=[self.domain, case._id]),
            'name': case.name,
            'externalId': case.external_id if case.external_id else '--',
            'phoneNumber': getattr(case, 'contact_phone_number', '--'),
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return AddCaseToGroup(self.request.POST)
        return AddCaseToGroup()

    def get_create_item_data(self, create_form):
        case_identifier = create_form.cleaned_data['case_identifier']
        case = get_case_by_identifier(self.domain, case_identifier)
        if case is None:
            return {
                'itemData': {
                    'id': case_identifier.replace(' ', '_'),
                    'identifier': case_identifier,
                    'message': _('Sorry, we could not a find a case that '
                                 'matched the identifier you provided.'),
                },
                'rowClass': 'warning',
                'template': 'case-message-template',
            }
        item_data = self._get_item_data(case)
        if case._id in self.case_group.cases:
            message = _('<span class="label label-important">Case already in group</span>')
        else:
            message = _('<span class="label label-success">Case added</span>')
            self.case_group.cases.append(case._id)
            self.case_group.save()
        item_data['message'] = message
        return {
            'itemData': item_data,
            'template': 'new-case-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

