import csv
import io
import uuid
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.cache import cache
from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain, \
    get_number_of_case_groups_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp.forms import BulkUploadForm
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.util.spreadsheets.excel import JSONReaderError, WorkbookJSONReader
from django.utils.decorators import method_decorator
from openpyxl.utils.exceptions import InvalidFileException
from corehq import CaseReassignmentInterface
from corehq.apps.data_interfaces.tasks import bulk_upload_cases_to_group, bulk_archive_forms
from corehq.apps.data_interfaces.forms import (
    AddCaseGroupForm, UpdateCaseGroupForm, AddCaseToGroupForm)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin, PaginatedItemException
from corehq.apps.reports.standard.export import ExcelExportReport
from corehq.apps.data_interfaces.dispatcher import (DataInterfaceDispatcher, EditDataInterfaceDispatcher,
                                                    require_can_edit_data)
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy


@login_and_domain_required
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()

    return HttpResponseRedirect(default_data_view_url(request, domain))


def default_data_view_url(request, domain):
    if request.couch_user.can_view_reports():
        return reverse(DataInterfaceDispatcher.name(), args=[domain, ExcelExportReport.slug])

    exportable_reports = request.couch_user.get_exportable_reports(domain)
    if exportable_reports:
        return reverse(DataInterfaceDispatcher.name(), args=[domain, exportable_reports[0]])

    if request.couch_user.can_edit_data():
        return reverse(EditDataInterfaceDispatcher.name(), args=[domain, CaseReassignmentInterface.slug])
    raise Http404()


class BulkUploadCasesException(Exception):
    pass


class DataInterfaceSection(BaseDomainView):
    section_name = ugettext_noop("Data")

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(DataInterfaceSection, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])


class CaseGroupListView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = "data_interfaces/list_case_groups.html"
    urlname = 'case_group_list'
    page_title = ugettext_lazy("Case Groups")

    limit_text = ugettext_lazy("groups per page")
    empty_notification = ugettext_lazy("You have no case groups. Please create one!")
    loading_message = ugettext_lazy("Loading groups...")
    deleted_items_header = ugettext_lazy("Deleted Groups:")
    new_items_header = ugettext_lazy("New Groups:")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        return get_number_of_case_groups_in_domain(self.domain)

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
        for group in get_case_groups_in_domain(
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
            'editUrl': reverse(CaseGroupCaseManagementView.urlname, args=[self.domain, case_group._id])
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

    def get_deleted_item_data(self, item_id):
        case_group = CommCareCaseGroup.get(item_id)
        item_data = self._get_item_data(case_group)
        case_group.soft_delete()
        return {
            'itemData': item_data,
            'template': 'deleted-group-template',
        }


class ArchiveFormView(DataInterfaceSection):
    template_name = 'data_interfaces/interfaces/import_forms.html'
    urlname = 'archive_forms'
    page_title = ugettext_noop("Bulk Archive Forms")

    ONE_MB = 1000000
    MAX_SIZE = 3 * ONE_MB

    @method_decorator(requires_privilege_with_fallback(privileges.BULK_CASE_MANAGEMENT))
    def dispatch(self, request, *args, **kwargs):
        if not toggles.BULK_ARCHIVE_FORMS.enabled(request.user.username):
            raise Http404()
        return super(ArchiveFormView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        context = {}
        context.update({
            'bulk_upload': {
                "download_url": static(
                    'data_interfaces/files/forms_bulk_example.xlsx'),
                "adjective": _("example"),
                "verb": _("archive"),
                "plural_noun": _("forms"),
            },
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    @property
    @memoized
    def uploaded_file(self):
        try:
            bulk_file = self.request.FILES['bulk_upload_file']
            if bulk_file.size > self.MAX_SIZE:
                raise BulkUploadCasesException(_(u"File size too large. "
                                                 "Please upload file less than"
                                                 " {size} Megabytes").format(size=self.MAX_SIZE / self.ONE_MB))

        except KeyError:
            raise BulkUploadCasesException(_("No files uploaded"))
        try:
            return WorkbookJSONReader(bulk_file)
        except InvalidFileException:
            try:
                csv.DictReader(io.StringIO(bulk_file.read().decode('utf-8'),
                                           newline=None))
                raise BulkUploadCasesException(_("CommCare HQ does not support that file type."
                                                 "Please convert to Excel 2007 or higher (.xlsx) "
                                                 "and try again."))
            except UnicodeDecodeError:
                raise BulkUploadCasesException(_("Unrecognized format"))
        except JSONReaderError as e:
            raise BulkUploadCasesException(_('Your upload was unsuccessful. %s') % e.message)

    def process(self):
        try:
            bulk_archive_forms.delay(
                self.domain,
                self.request.user,
                list(self.uploaded_file.get_worksheet())
            )
            messages.success(self.request, _("We received your file and are processing it. "
                                             "You will receive an email when it has finished."))
        except BulkUploadCasesException as e:
            messages.error(self.request, e.message)
        return None

    def post(self, request, *args, **kwargs):
        self.process()
        return HttpResponseRedirect(self.page_url)


class CaseGroupCaseManagementView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = 'data_interfaces/manage_case_groups.html'
    urlname = 'manage_case_groups'
    page_title = ugettext_noop("Manage Case Group")

    limit_text = ugettext_noop("cases per page")
    empty_notification = ugettext_noop("You have no cases in your group.")
    loading_message = ugettext_noop("Loading cases...")
    deleted_items_header = ugettext_noop("Removed Cases:")
    new_items_header = ugettext_noop("Added Cases:")

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
        context = self.pagination_context
        context.update({
            'bulk_upload': {
                "download_url": static(
                    'data_interfaces/files/cases_bulk_example.xlsx'),
                "adjective": _("case"),
                "plural_noun": _("cases"),
            },
            'bulk_upload_id': self.bulk_upload_id,
            'update_case_group_form': self.update_case_group_form,
            'group_name': self.case_group.name,
        })
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    @property
    @memoized
    def update_case_group_form(self):
        initial = {
            'name': self.case_group.name,
            'item_id': self.case_group._id,
        }
        if self.is_case_group_update:
            return UpdateCaseGroupForm(self.request.POST, initial=initial)
        return UpdateCaseGroupForm(initial=initial)

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        return self.case_group.get_total_cases()

    @property
    def column_names(self):
        return [
            _("Case Name"),
            _("Phone Number"),
            _("External ID"),
            _("Action"),
        ]

    @property
    def paginated_list(self):
        for case in self.case_group.get_cases(limit=self.limit, skip=self.skip):
            yield {
                'itemData': self._get_item_data(case),
                'template': 'existing-case-template',
            }

    @property
    def allowed_actions(self):
        actions = super(CaseGroupCaseManagementView, self).allowed_actions
        actions.append('bulk')
        return actions

    @property
    def bulk_response(self):
        return cache.get(self.request.POST['upload_id'])

    @property
    def is_bulk_upload(self):
        return self.request.method == 'POST' and self.request.POST.get('action') == 'bulk_upload'

    @property
    def is_case_group_update(self):
        return self.request.method == 'POST' and self.request.POST.get('action') == 'update_case_group'

    @property
    def bulk_upload_id(self):
        if not self.is_bulk_upload:
            return None
        try:
            if self.uploaded_file:
                upload_id = uuid.uuid4().hex
                bulk_upload_cases_to_group.delay(
                    upload_id,
                    self.domain,
                    self.group_id,
                    list(self.uploaded_file.get_worksheet())
                )
                messages.success(self.request, _("We received your file and are processing it..."))
                return upload_id
        except BulkUploadCasesException as e:
            messages.error(self.request, e.message)
        return None

    @property
    @memoized
    def uploaded_file(self):
        try:
            bulk_file = self.request.FILES['bulk_upload_file']
        except KeyError:
            raise BulkUploadCasesException(_("No files uploaded"))
        try:
            return WorkbookJSONReader(bulk_file)
        except InvalidFileException:
            try:
                csv.DictReader(io.StringIO(bulk_file.read().decode('ascii'),
                                           newline=None))
                raise BulkUploadCasesException(_("CommCare HQ no longer supports CSV upload. "
                                                 "Please convert to Excel 2007 or higher (.xlsx) "
                                                 "and try again."))
            except UnicodeDecodeError:
                raise BulkUploadCasesException(_("Unrecognized format"))
        except JSONReaderError as e:
            raise BulkUploadCasesException(_('Your upload was unsuccessful. %s') % e.message)

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
            return AddCaseToGroupForm(self.request.POST)
        return AddCaseToGroupForm()

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
            message = '<span class="label label-important">%s</span>' % _("Case already in group")
        elif case.doc_type != 'CommCareCase':
            message = '<span class="label label-important">%s</span>' % _("It looks like this case was deleted.")
        else:
            message = '<span class="label label-success">%s</span>' % _("Case added")
            self.case_group.cases.append(case._id)
            self.case_group.save()
        item_data['message'] = message
        return {
            'itemData': item_data,
            'template': 'new-case-template',
        }

    def get_deleted_item_data(self, item_id):
        if not item_id:
            raise PaginatedItemException("The case's ID was blank.")
        current_cases = set(self.case_group.cases)
        self.case_group.cases = list(current_cases.difference([item_id]))
        self.case_group.save()
        return {
            'template': 'removed-case-template',
        }

    def post(self, request, *args, **kwargs):
        if self.is_bulk_upload or self.is_case_group_update:
            if self.is_case_group_update and self.update_case_group_form.is_valid():
                self.update_case_group_form.update_group()
                return HttpResponseRedirect(self.page_url)
            return self.get(request, *args, **kwargs)
        return self.paginate_crud_response
