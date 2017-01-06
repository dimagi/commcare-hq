import csv
import io
import json
import uuid
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.cache import cache
from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.app_manager.util import all_case_properties_by_domain
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain, \
    get_number_of_case_groups_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.users.permissions import can_view_form_exports, can_view_case_exports
from corehq.util.workbook_json.excel import JSONReaderError, WorkbookJSONReader, \
    InvalidExcelFileException
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from django.utils.decorators import method_decorator
from corehq.apps.data_interfaces.tasks import (
    bulk_upload_cases_to_group, bulk_archive_forms, bulk_form_management_async)
from corehq.apps.data_interfaces.forms import (
    AddCaseGroupForm, UpdateCaseGroupForm, AddCaseToGroupForm,
    AddAutomaticCaseUpdateRuleForm)
from corehq.apps.data_interfaces.models import (AutomaticUpdateRule,
                                                AutomaticUpdateRuleCriteria,
                                                AutomaticUpdateAction)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin, PaginatedItemException
from corehq.apps.data_interfaces.dispatcher import (
    EditDataInterfaceDispatcher,
    require_can_edit_data,
)
from corehq.apps.style.decorators import use_typeahead, use_angular_js
from corehq.const import SERVER_DATETIME_FORMAT
from .dispatcher import require_form_management_privilege
from .interfaces import FormManagementMode, BulkFormManagementInterface
from django.db import transaction
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseServerError
from django.shortcuts import render
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context


@login_and_domain_required
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()

    return HttpResponseRedirect(default_data_view_url(request, domain))


def default_data_view_url(request, domain):
    from corehq.apps.export.views import (
        FormExportListView, CaseExportListView,
        DeIdFormExportListView, user_can_view_deid_exports
    )
    if can_view_form_exports(request.couch_user, domain):
        return reverse(FormExportListView.urlname, args=[domain])
    elif can_view_case_exports(request.couch_user, domain):
        return reverse(CaseExportListView.urlname, args=[domain])

    if user_can_view_deid_exports(domain, request.couch_user):
        return reverse(DeIdFormExportListView.urlname, args=[domain])

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
                    'data_interfaces/xlsx/forms_bulk_example.xlsx'),
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
        except InvalidExcelFileException:
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
                self.request.couch_user,
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
                    'data_interfaces/xlsx/cases_bulk_example.xlsx'),
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
        except InvalidExcelFileException:
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
            'id': case.case_id,
            'detailsUrl': reverse('case_details', args=[self.domain, case.case_id]),
            'name': case.name,
            'externalId': case.external_id if case.external_id else '--',
            'phoneNumber': case.get_case_property('contact_phone_number') or '--',
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
        if case.case_id in self.case_group.cases:
            message = '<span class="label label-danger">%s</span>' % _("Case already in group")
        elif case.doc_type != 'CommCareCase':
            message = '<span class="label label-danger">%s</span>' % _("It looks like this case was deleted.")
        else:
            message = '<span class="label label-success">%s</span>' % _("Case added")
            self.case_group.cases.append(case.case_id)
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


class XFormManagementView(DataInterfaceSection):
    urlname = 'xform_management'
    page_title = ugettext_noop('Form Management')

    def get_form_ids_or_query_string(self, request):
        if 'select_all' in self.request.POST:
            # Altough evaluating form_ids and sending to task would be cleaner,
            # heavier calls should be in in an async task instead
            import urllib
            form_query_string = urllib.unquote(self.request.POST.get('select_all'))
            return form_query_string
        else:
            return self.request.POST.getlist('xform_ids')

    def post(self, request, *args, **kwargs):
        form_ids_or_query_string = self.get_form_ids_or_query_string(request)
        mode = self.request.POST.get('mode')
        task_ref = expose_cached_download(payload=None, expiry=1*60*60, file_extension=None)
        task = bulk_form_management_async.delay(
            mode,
            self.domain,
            self.request.couch_user,
            form_ids_or_query_string
        )
        task_ref.set_task(task)

        return HttpResponseRedirect(
            reverse(
                XFormManagementStatusView.urlname,
                args=[self.domain, mode, task_ref.download_id]
            )
        )

    @method_decorator(require_form_management_privilege)
    def dispatch(self, request, *args, **kwargs):
        return super(XFormManagementView, self).dispatch(request, *args, **kwargs)


class XFormManagementStatusView(DataInterfaceSection):

    urlname = 'xform_management_status'
    page_title = ugettext_noop('Form Status')

    def get(self, request, *args, **kwargs):
        context = super(XFormManagementStatusView, self).main_context
        mode = FormManagementMode(kwargs['mode'])

        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': "{url}?mode={mode}".format(
                url=reverse('xform_management_job_poll', args=[self.domain, kwargs['download_id']]),
                mode=mode.mode_name),
            'title': mode.status_page_title,
            'error_text': mode.error_text,
        })
        return render(request, 'style/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_data
@require_form_management_privilege
def xform_management_job_poll(request, domain, download_id,
                              template="data_interfaces/partials/xform_management_status.html"):
    mode = FormManagementMode(request.GET.get('mode'), validate=True)
    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': mode.complete_short,
        'mode': mode,
        'form_management_url': reverse(EditDataInterfaceDispatcher.name(),
                                       args=[domain, BulkFormManagementInterface.slug])
    })
    return render(request, template, context)


class AutomaticUpdateRuleListView(JSONResponseMixin, DataInterfaceSection):
    template_name = 'data_interfaces/list_automatic_update_rules.html'
    urlname = 'automatic_update_rule_list'
    page_title = ugettext_lazy("Automatically Close Cases")

    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_DELETE = 'delete'

    @property
    @memoized
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    @use_angular_js
    @method_decorator(requires_privilege_with_fallback(privileges.DATA_CLEANUP))
    def dispatch(self, *args, **kwargs):
        return super(AutomaticUpdateRuleListView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        return {
            'pagination_limit_cookie_name': ('hq.pagination.limit'
                                             '.automatic_update_rule_list.%s'
                                             % self.domain),
            'help_site_url': 'https://confluence.dimagi.com/display/commcarepublic/Automatically+Close+Cases',
        }

    def _format_rule(self, rule):
        return {
            'id': rule.pk,
            'name': rule.name,
            'case_type': rule.case_type,
            'active': rule.active,
            'last_run': (ServerTime(rule.last_run)
                         .user_time(self.project_timezone)
                         .done()
                         .strftime(SERVER_DATETIME_FORMAT)) if rule.last_run else '-',
            'edit_url': reverse(EditAutomaticUpdateRuleView.urlname, args=[self.domain, rule.pk]),
        }

    @allow_remote_invocation
    def get_pagination_data(self, in_data):
        try:
            limit = int(in_data['limit'])
            page = int(in_data['page'])
        except (TypeError, KeyError, ValueError):
            return {
                'success': False,
                'error': _("Please provide pagination info."),
            }

        start = (page - 1) * limit
        stop = limit * page

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain,
            deleted=False
        ).order_by('name')[start:stop]

        total = AutomaticUpdateRule.objects.filter(
            domain=self.domain,
            deleted=False
        ).count()

        return {
            'response': {
                'itemList': map(self._format_rule, rules),
                'total': total,
                'page': page,
            },
            'success': True,
        }

    @allow_remote_invocation
    def update_rule(self, in_data):
        try:
            rule_id = in_data['id']
        except KeyError:
            return {
                'error': _("Please provide an id."),
            }

        try:
            action = in_data['update_action']
        except KeyError:
            return {
                'error': _("Please provide an update_action."),
            }

        if action not in (
            self.ACTION_ACTIVATE,
            self.ACTION_DEACTIVATE,
            self.ACTION_DELETE,
        ):
            return {
                'error': _("Unrecognized update_action."),
            }

        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id)
        except AutomaticUpdateRule.DoesNotExist:
            return {
                'error': _("Rule not found."),
            }

        if rule.domain != self.domain:
            return {
                'error': _("Rule not found."),
            }

        if action == self.ACTION_ACTIVATE:
            rule.activate()
        elif action == self.ACTION_DEACTIVATE:
            rule.activate(False)
        elif action == self.ACTION_DELETE:
            rule.soft_delete()

        return {
            'success': True,
        }


class AddAutomaticUpdateRuleView(JSONResponseMixin, DataInterfaceSection):
    template_name = 'data_interfaces/add_automatic_update_rule.html'
    urlname = 'add_automatic_update_rule'
    page_title = ugettext_lazy("Add Automatic Case Close Rule")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def initial_rule_form(self):
        return AddAutomaticCaseUpdateRuleForm(
            domain=self.domain,
            initial={
                'action': AddAutomaticCaseUpdateRuleForm.ACTION_CLOSE,
                'property_value_type': AutomaticUpdateAction.EXACT,
            }
        )

    @property
    @memoized
    def rule_form(self):
        if self.request.method == 'POST':
            return AddAutomaticCaseUpdateRuleForm(self.request.POST, domain=self.domain)
        else:
            return self.initial_rule_form

    @property
    def page_context(self):
        return {
            'form': self.rule_form,
        }

    @allow_remote_invocation
    def get_case_property_map(self):
        data = all_case_properties_by_domain(self.domain,
            include_parent_properties=False)
        return {
            'data': data,
            'success': True,
        }

    @use_angular_js
    @use_typeahead
    @method_decorator(requires_privilege_with_fallback(privileges.DATA_CLEANUP))
    def dispatch(self, *args, **kwargs):
        return super(AddAutomaticUpdateRuleView, self).dispatch(*args, **kwargs)

    def create_criteria(self, rule):
        for condition in self.rule_form.cleaned_data['conditions']:
            AutomaticUpdateRuleCriteria.objects.create(
                rule=rule,
                property_name=condition['property_name'],
                property_value=condition['property_value'],
                match_type=condition['property_match_type'],
            )

    def create_actions(self, rule):
        if self.rule_form._closes_case():
            AutomaticUpdateAction.objects.create(
                rule=rule,
                action=AutomaticUpdateAction.ACTION_CLOSE,
            )
        if self.rule_form._updates_case():
            AutomaticUpdateAction.objects.create(
                rule=rule,
                action=AutomaticUpdateAction.ACTION_UPDATE,
                property_name=self.rule_form.cleaned_data['update_property_name'],
                property_value=self.rule_form.cleaned_data['update_property_value'],
                property_value_type=self.rule_form.cleaned_data['property_value_type']
            )

    def create_rule(self):
        with transaction.atomic():
            rule = AutomaticUpdateRule.objects.create(
                domain=self.domain,
                name=self.rule_form.cleaned_data['name'],
                case_type=self.rule_form.cleaned_data['case_type'],
                active=True,
                server_modified_boundary=self.rule_form.cleaned_data['server_modified_boundary'],
                filter_on_server_modified=self.rule_form.cleaned_data['filter_on_server_modified'],
            )
            self.create_criteria(rule)
            self.create_actions(rule)

    def post(self, request, *args, **kwargs):
        if self.rule_form.is_valid():
            self.create_rule()
            return HttpResponseRedirect(reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]))
        # We can't call self.get() because JSONResponseMixin gets confused
        # since we're processing a post request. So instead we have to call
        # .get() directly on super(JSONResponseMixin, self), which correctly
        # is DataInterfaceSection in this case
        return super(JSONResponseMixin, self).get(request, *args, **kwargs)


class EditAutomaticUpdateRuleView(AddAutomaticUpdateRuleView):
    urlname = 'edit_automatic_update_rule'
    page_title = ugettext_lazy("Edit Automatic Case Close Rule")

    @property
    @memoized
    def rule_id(self):
        return self.kwargs.get('rule_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

    @property
    @memoized
    def rule(self):
        try:
            rule = AutomaticUpdateRule.objects.get(pk=self.rule_id)
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

        if rule.domain != self.domain or rule.deleted:
            raise Http404()

        return rule

    @property
    def initial_rule_form(self):
        conditions = []
        for criterion in self.rule.automaticupdaterulecriteria_set.order_by('property_name'):
            conditions.append({
                'property_name': criterion.property_name,
                'property_match_type': criterion.match_type,
                'property_value': criterion.property_value,
            })

        close_case = False
        update_case = False
        update_property_name = None
        update_property_value = None
        property_value_type = AutomaticUpdateAction.EXACT
        for action in self.rule.automaticupdateaction_set.all():
            if action.action == AutomaticUpdateAction.ACTION_UPDATE:
                update_case = True
                update_property_name = action.property_name
                update_property_value = action.property_value
                property_value_type = action.property_value_type
            elif action.action == AutomaticUpdateAction.ACTION_CLOSE:
                close_case = True

        if close_case and update_case:
            initial_action = AddAutomaticCaseUpdateRuleForm.ACTION_UPDATE_AND_CLOSE
        elif update_case and not close_case:
            initial_action = AddAutomaticCaseUpdateRuleForm.ACTION_UPDATE
        else:
            initial_action = AddAutomaticCaseUpdateRuleForm.ACTION_CLOSE

        initial = {
            'name': self.rule.name,
            'case_type': self.rule.case_type,
            'server_modified_boundary': self.rule.server_modified_boundary,
            'conditions': json.dumps(conditions),
            'action': initial_action,
            'update_property_name': update_property_name,
            'update_property_value': update_property_value,
            'property_value_type': property_value_type,
            'filter_on_server_modified': json.dumps(self.rule.filter_on_server_modified),
        }
        return AddAutomaticCaseUpdateRuleForm(domain=self.domain, initial=initial)

    @property
    @memoized
    def rule_form(self):
        if self.request.method == 'POST':
            return AddAutomaticCaseUpdateRuleForm(
                self.request.POST,
                domain=self.domain,
                # Pass the original case_type so that we can always continue to
                # properly display and edit rules based off of deleted case types
                initial={'case_type': self.rule.case_type}
            )
        else:
            return self.initial_rule_form

    def update_rule(self, rule):
        with transaction.atomic():
            rule.name = self.rule_form.cleaned_data['name']
            rule.case_type = self.rule_form.cleaned_data['case_type']
            rule.server_modified_boundary = self.rule_form.cleaned_data['server_modified_boundary']
            rule.filter_on_server_modified = self.rule_form.cleaned_data['filter_on_server_modified']
            rule.last_run = None
            rule.save()
            rule.automaticupdaterulecriteria_set.all().delete()
            rule.automaticupdateaction_set.all().delete()
            self.create_criteria(rule)
            self.create_actions(rule)

    def post(self, request, *args, **kwargs):
        if self.rule_form.is_valid():
            self.update_rule(self.rule)
            return HttpResponseRedirect(reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]))
        return super(JSONResponseMixin, self).get(request, *args, **kwargs)
