import json
import uuid

from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.http import require_GET

from couchdbkit import ResourceNotFound
from memoized import memoized
from no_exceptions.exceptions import Http403

from casexml.apps.case import const
from dimagi.utils.logging import notify_exception
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.case_search.const import SPECIAL_CASE_PROPERTIES
from corehq.apps.casegroups.dbaccessors import (
    get_case_groups_in_domain,
    get_number_of_case_groups_in_domain,
)
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.data_dictionary.util import (
    get_data_dict_props_by_case_type,
    is_case_type_deprecated,
)
from corehq.apps.data_interfaces.deduplication import (
    reset_and_backfill_deduplicate_rule,
)
from corehq.apps.data_interfaces.dispatcher import (
    EditDataInterfaceDispatcher,
    require_can_edit_data,
)
from corehq.apps.data_interfaces.forms import (
    AddCaseGroupForm,
    AddCaseToGroupForm,
    CaseRuleActionsForm,
    CaseRuleCriteriaForm,
    CaseUpdateRuleForm,
    DedupeCaseFilterForm,
    UpdateCaseGroupForm,
)
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDuplicateNew,
    DomainCaseRuleRun,
)
from corehq.apps.data_interfaces.tasks import (
    bulk_form_management_async,
    bulk_upload_cases_to_group,
)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqcase.case_helper import CaseCopier
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.models import PageInfoContext
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.hqwebapp.views import (
    CRUDPaginatedViewMixin,
    PaginatedItemException,
)
from corehq.apps.locations.dbaccessors import user_ids_at_accessible_locations
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.reports.standard.cases.filters import CaseListExplorerColumns
from corehq.apps.reports.v2.reports.explore_case_data import (
    ExploreCaseDataReport,
)
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.apps.users.permissions import can_download_data_files
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.form_processor.models import XFormInstance
from corehq.messaging.util import MessagingRuleProgressHelper
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import reverse as reverse_with_params
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook

from ..users.decorators import require_permission
from ..users.models import HqPermissions
from .dispatcher import require_form_management_privilege
from .interfaces import (
    BulkFormManagementInterface,
    CaseCopyInterface,
    CaseReassignmentInterface,
    FormManagementMode,
)


@login_and_domain_required
@location_safe
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()

    return HttpResponseRedirect(default_data_view_url(request, domain))


def default_data_view_url(request, domain):
    from corehq.apps.data_interfaces.interfaces import (
        CaseReassignmentInterface,
    )
    from corehq.apps.export.views.list import (
        CaseExportListView,
        DeIdFormExportListView,
        FormExportListView,
    )
    from corehq.apps.export.views.utils import (
        DataFileDownloadList,
        can_view_case_exports,
        can_view_form_exports,
        user_can_view_deid_exports,
    )

    if can_view_form_exports(request.couch_user, domain):
        return reverse(FormExportListView.urlname, args=[domain])
    elif can_view_case_exports(request.couch_user, domain):
        return reverse(CaseExportListView.urlname, args=[domain])

    if user_can_view_deid_exports(domain, request.couch_user):
        return reverse(DeIdFormExportListView.urlname, args=[domain])

    if can_download_data_files(domain, request.couch_user):
        return reverse(DataFileDownloadList.urlname, args=[domain])

    if request.couch_user.can_edit_data():
        return CaseReassignmentInterface.get_url(domain)

    raise Http404()


class BulkUploadCasesException(Exception):
    pass


class DataInterfaceSection(BaseDomainView):
    section_name = gettext_noop("Data")
    urlname = 'data_interfaces_default'

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(DataInterfaceSection, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])


@location_safe
class ExploreCaseDataView(BaseDomainView):
    template_name = "data_interfaces/explore_case_data.html"
    urlname = "explore_case_data"
    page_title = gettext_lazy("Explore Case Data")

    @use_daterangepicker
    def dispatch(self, request, *args, **kwargs):
        if hasattr(request, 'couch_user') and not self.report_config.has_permission:
            raise Http404()
        return super(ExploreCaseDataView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse("data_interfaces_default", args=[self.domain])

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def report_config(self):
        return ExploreCaseDataReport(self.request, self.domain)

    @property
    def page_context(self):
        return {
            'report': self.report_config.context,
            'section': PageInfoContext(
                title=DataInterfaceSection.section_name,
                url=reverse(DataInterfaceSection.urlname, args=[self.domain]),
            ),
            'page': PageInfoContext(
                title=self.page_title,
                url=reverse(self.urlname, args=[self.domain]),
            ),
        }


class CaseGroupListView(BaseMessagingSectionView, CRUDPaginatedViewMixin):
    template_name = "data_interfaces/list_case_groups.html"
    urlname = 'case_group_list'
    page_title = gettext_lazy("Case Groups")

    limit_text = gettext_lazy("groups per page")
    empty_notification = gettext_lazy("You have no case groups. Please create one!")
    loading_message = gettext_lazy("Loading groups...")
    deleted_items_header = gettext_lazy("Deleted Groups:")
    new_items_header = gettext_lazy("New Groups:")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

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
        for group in get_case_groups_in_domain(self.domain)[self.skip:self.skip + self.limit]:
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


@method_decorator(require_permission(HqPermissions.edit_messaging), name="dispatch")
class CaseGroupCaseManagementView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = 'data_interfaces/manage_case_groups.html'
    urlname = 'manage_case_groups'
    page_title = gettext_noop("Manage Case Group")

    limit_text = gettext_noop("cases per page")
    empty_notification = gettext_noop("You have no cases in your group.")
    loading_message = gettext_noop("Loading cases...")
    deleted_items_header = gettext_noop("Removed Cases:")
    new_items_header = gettext_noop("Added Cases:")

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
            messages.error(self.request, str(e))
        return None

    @property
    @memoized
    def uploaded_file(self):
        try:
            bulk_file = self.request.FILES['bulk_upload_file']
        except KeyError:
            raise BulkUploadCasesException(_("No files uploaded"))
        try:
            return get_workbook(bulk_file)
        except WorkbookJSONError as e:
            raise BulkUploadCasesException(str(e))

    def _get_item_data(self, case):
        return {
            'id': case.case_id,
            'detailsUrl': reverse('case_data', args=[self.domain, case.case_id]),
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


@location_safe
class XFormManagementView(DataInterfaceSection):
    urlname = 'xform_management'
    page_title = gettext_noop('Form Management')

    def post(self, request, *args, **kwargs):
        form_ids = self.get_xform_ids(request)
        if not self.request.can_access_all_locations:
            inaccessible_forms_accessed = self.inaccessible_forms_accessed(
                form_ids, self.domain, request.couch_user)
            if inaccessible_forms_accessed:
                return HttpResponseBadRequest(
                    "Inaccessible forms accessed. Id(s): %s " % ','.join(inaccessible_forms_accessed))

        mode = self.request.POST.get('mode')
        task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
        task = bulk_form_management_async.delay(
            mode,
            self.domain,
            self.request.couch_user,
            form_ids
        )
        task_ref.set_task(task)

        return HttpResponseRedirect(
            reverse(
                XFormManagementStatusView.urlname,
                args=[self.domain, mode, task_ref.download_id]
            )
        )

    def inaccessible_forms_accessed(self, xform_ids, domain, couch_user):
        xforms = XFormInstance.objects.get_forms(xform_ids, domain)
        xforms_user_ids = set([xform.user_id for xform in xforms])
        accessible_user_ids = set(user_ids_at_accessible_locations(domain, couch_user))
        return xforms_user_ids - accessible_user_ids

    def get_xform_ids(self, request):
        if 'select_all' in self.request.POST:
            # Altough evaluating form_ids and sending to task would be cleaner,
            # heavier calls should be in an async task instead
            from urllib.parse import unquote

            from django.http import HttpRequest, QueryDict

            from django_otp.middleware import OTPMiddleware

            form_query_string = unquote(self.request.POST.get('select_all'))
            _request = HttpRequest()
            _request.couch_user = request.couch_user
            _request.user = request.couch_user.get_django_user()
            _request.domain = self.domain
            _request.couch_user.current_domain = self.domain
            _request.can_access_all_locations = request.couch_user.has_permission(self.domain,
                                                                                  'access_all_locations')
            _request.always_allow_project_access = True
            _request.session = request.session

            _request.GET = QueryDict(form_query_string)
            OTPMiddleware(lambda req: None)(_request)

            dispatcher = EditDataInterfaceDispatcher()
            xform_ids = dispatcher.dispatch(
                _request,
                render_as='form_ids',
                domain=self.domain,
                report_slug=BulkFormManagementInterface.slug,
                skip_permissions_check=True,
            )
        else:
            xform_ids = self.request.POST.getlist('xform_ids')

        return xform_ids

    @method_decorator(require_form_management_privilege)
    def dispatch(self, request, *args, **kwargs):
        return super(XFormManagementView, self).dispatch(request, *args, **kwargs)


@location_safe
class XFormManagementStatusView(DataInterfaceSection):

    urlname = 'xform_management_status'
    page_title = gettext_noop('Form Status')

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
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@location_safe
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


class BulkCaseActionSatusView(DataInterfaceSection):
    urlname = "bulk_case_action_status"

    @property
    def section_url(self):
        interface_class = CaseReassignmentInterface
        if self.is_copy_action:
            interface_class = CaseCopyInterface

        return interface_class.get_url(self.domain)

    @property
    def page_title(self):
        title = "Bulk Case Reassignment Status"
        if self.is_copy_action:
            title = "Bulk Case Copy Status"
        return gettext_noop(title)

    def get(self, request, *args, **kwargs):
        if self.is_copy_action:
            action_text = "Copying"
        else:
            action_text = "Reassigning"

        context = super(BulkCaseActionSatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': self.poll_url(kwargs['download_id']),
            'title': _(self.page_title),
            'progress_text': _("{action_text} Cases. This may take some time...").format(action_text=action_text),
            'error_text': _(
                "Bulk Case {action_text} failed for some reason and we have noted this failure."
            ).format(action_text=action_text),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def poll_url(self, download_id):
        return reverse(
            'case_action_job_poll',
            args=[self.domain, download_id]
        ) + f"?action={self.case_action}"

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)

    @property
    def case_action(self):
        return self.request.GET.get('action', CaseReassignmentInterface.action)

    @property
    def is_copy_action(self):
        return self.case_action == CaseCopyInterface.action


def case_action_job_poll(request, domain, download_id):
    try:
        context = get_download_context(download_id, require_result=True)
    except TaskFailedError as e:
        notify_exception(request, message=str(e))
        return HttpResponseServerError()

    case_action = request.GET.get('action', CaseReassignmentInterface.action)
    if case_action == CaseCopyInterface.action:
        template = "data_interfaces/partials/case_copy_status.html"
    else:
        template = "data_interfaces/partials/case_reassign_status.html"

    return render(request, template, context)


@login_and_domain_required
@require_GET
def find_by_id(request, domain):
    from corehq.apps.export.views.utils import (
        can_view_case_exports,
        can_view_form_exports,
    )
    can_view_cases = can_view_case_exports(request.couch_user, domain)
    can_view_forms = can_view_form_exports(request.couch_user, domain)

    if not can_view_cases and not can_view_forms:
        raise Http403()

    name = _("Find Data by ID")
    return render(request, 'data_interfaces/find_by_id.html', {
        'domain': domain,
        'current_page': {
            'title': name,
            'page_name': name,
        },
        'section': {
            'page_name': DataInterfaceSection.section_name,
            'url': reverse(DataInterfaceSection.urlname, args=[domain]),
        },
        'can_view_cases': can_view_cases,
        'can_view_forms': can_view_forms,
    })


class AutomaticUpdateRuleListView(DataInterfaceSection):
    template_name = 'data_interfaces/auto_update_rules.html'
    urlname = 'automatic_update_rule_list'
    page_title = gettext_lazy("Automatically Update Cases")

    limit_text = gettext_lazy("rules per page")
    empty_notification = gettext_lazy("You have no case rules.")
    loading_message = gettext_lazy("Loading rules...")
    deleted_items_header = gettext_lazy("Deleted Rules")

    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_DELETE = 'delete'

    rule_workflow = AutomaticUpdateRule.WORKFLOW_CASE_UPDATE

    @method_decorator(requires_privilege_with_fallback(privileges.DATA_CLEANUP))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        context = super().page_context
        domain_obj = Domain.get_by_name(self.domain)
        hour = domain_obj.auto_case_update_hour
        context.update({
            'rules': [self._format_rule(rule) for rule in self._rules()],
            'time': f"{hour}:00" if hour else _('midnight'),  # noqa: E999
            'rule_runs': [self._format_rule_run(run) for run in self._rule_runs()],
            'has_linked_data': self.has_linked_data(),
            'can_edit_linked_data': self.can_edit_linked_data(),
        })
        return context

    def has_linked_data(self):
        return bool(self._rules().exclude(upstream_id=None)[:1])

    def can_edit_linked_data(self):
        return self.request.couch_user.can_edit_linked_data(self.domain)

    def post(self, request, *args, **kwargs):
        response = self._update_rule(request.POST['id'], request.POST['action'])
        return JsonResponse(response)

    @property
    def edit_url_name(self):
        return EditCaseRuleView.urlname

    @property
    def view_url_name(self):
        return ViewCaseRuleView.urlname

    def _format_rule(self, rule):
        return {
            'id': rule.pk,
            'name': rule.name,
            'case_type': rule.case_type,
            'is_case_type_deprecated': is_case_type_deprecated(self.domain, rule.case_type),
            'active': rule.active,
            'last_run': self._convert_to_user_time(rule.last_run),
            'edit_url': reverse(self.edit_url_name, args=[self.domain, rule.pk]),
            'view_url': reverse(self.view_url_name, args=[self.domain, rule.pk]),
            'action_error': "",     # must be provided because knockout template looks for it
            'upstream_id': rule.upstream_id,
        }

    def _format_rule_run(self, rule_run):
        return {
            'case_type': rule_run.case_type,
            'status': rule_run.get_status_display(),
            'started_on': self._convert_to_user_time(rule_run.started_on),
            'finished_on': self._convert_to_user_time(rule_run.finished_on),
            'cases_updated': rule_run.num_updates,
            'cases_closed': rule_run.num_closes,
        }

    def _convert_to_user_time(self, value):
        return (ServerTime(value)
                .user_time(get_timezone_for_user(None, self.domain))
                .done()
                .strftime(SERVER_DATETIME_FORMAT)) if value else '-'

    @memoized
    def _rules(self):
        return AutomaticUpdateRule.by_domain(
            self.domain,
            self.rule_workflow,
            active_only=False,
        ).order_by('name', 'id')

    @memoized
    def _rule_runs(self):
        return DomainCaseRuleRun.objects.filter(
            domain=self.domain,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        ).order_by('-started_on', '-finished_on')

    def _update_rule(self, rule_id, action):
        rule, error = self._get_rule(rule_id)
        if rule is None:
            return {'success': False, 'error': error}

        if action == self.ACTION_ACTIVATE:
            rule.activate()
        elif action == self.ACTION_DEACTIVATE:
            rule.activate(False)
        elif action == self.ACTION_DELETE:
            rule.soft_delete()

        return {'success': True, 'itemData': self._format_rule(rule)}

    def _get_rule(self, rule_id):
        if rule_id is None:
            return None, _("Please provide an id.")

        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id, workflow=self.rule_workflow)
        except AutomaticUpdateRule.DoesNotExist:
            return None, _("Rule not found.")

        if rule.domain != self.domain:
            return None, _("Rule not found.")

        return rule, None


class AddCaseRuleView(DataInterfaceSection):
    template_name = "data_interfaces/case_rule.html"
    urlname = 'add_case_rule'
    page_title = gettext_lazy("Add Case Rule")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def initial_rule(self):
        return None

    @property
    @memoized
    def is_system_admin(self):
        return self.request.couch_user.is_superuser

    @property
    @memoized
    def read_only_mode(self):
        return self.requires_system_admin()

    def requires_system_admin(self):
        return not self.is_system_admin and (
            self.criteria_form.requires_system_admin_to_edit
            or self.actions_form.requires_system_admin_to_edit
        )

    @property
    @memoized
    def rule_form(self):
        if self.request.method == 'POST':
            return CaseUpdateRuleForm(self.domain, self.request.POST, rule=self.initial_rule,
                is_system_admin=self.is_system_admin)

        return CaseUpdateRuleForm(self.domain, rule=self.initial_rule, is_system_admin=self.is_system_admin)

    @property
    @memoized
    def criteria_form(self):
        if self.request.method == 'POST':
            return CaseRuleCriteriaForm(self.domain, self.request.POST, rule=self.initial_rule,
                is_system_admin=self.is_system_admin)

        return CaseRuleCriteriaForm(self.domain, rule=self.initial_rule, is_system_admin=self.is_system_admin)

    @property
    @memoized
    def actions_form(self):
        if self.request.method == 'POST':
            return CaseRuleActionsForm(self.domain, self.request.POST, rule=self.initial_rule,
                is_system_admin=self.is_system_admin)

        return CaseRuleActionsForm(self.domain, rule=self.initial_rule, is_system_admin=self.is_system_admin)

    @property
    def page_context(self):
        return {
            'rule_form': self.rule_form,
            'criteria_form': self.criteria_form,
            'actions_form': self.actions_form,
            'read_only_mode': self.read_only_mode,
            'requires_sysadmin': self.requires_system_admin(),
            'all_case_properties': {
                t: sorted(names) for t, names in
                get_data_dict_props_by_case_type(self.domain).items()
            },
        }

    def post(self, request, *args, **kwargs):
        rule_form_valid = self.rule_form.is_valid()
        criteria_form_valid = self.criteria_form.is_valid()
        actions_form_valid = self.actions_form.is_valid()

        if self.read_only_mode:
            # Don't allow making changes to rules that have custom
            # criteria/actions unless the user has permission to
            return HttpResponseBadRequest()

        if rule_form_valid and criteria_form_valid and actions_form_valid:
            if not self.is_system_admin and (
                self.criteria_form.requires_system_admin_to_save
                or self.actions_form.requires_system_admin_to_save
            ):
                # Don't allow adding custom criteria/actions to rules
                # unless the user has permission to
                return HttpResponseBadRequest()

            with transaction.atomic():
                if self.initial_rule:
                    rule = self.initial_rule
                else:
                    rule = AutomaticUpdateRule(
                        domain=self.domain,
                        active=True,
                        workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                    )

                rule.name = self.rule_form.cleaned_data['name']
                self.criteria_form.save_criteria(rule)
                self.actions_form.save_actions(rule)
            return HttpResponseRedirect(reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]))

        return self.get(request, *args, **kwargs)


class EditCaseRuleView(AddCaseRuleView):
    urlname = 'edit_case_rule'
    page_title = gettext_lazy("Edit Case Rule")

    rule_workflow = AutomaticUpdateRule.WORKFLOW_CASE_UPDATE

    @property
    @memoized
    def rule_id(self):
        return self.kwargs.get('rule_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

    @property
    @memoized
    def initial_rule(self):
        try:
            rule = AutomaticUpdateRule.objects.get(
                pk=self.rule_id,
                workflow=self.rule_workflow,
            )
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

        if rule.domain != self.domain or rule.deleted:
            raise Http404()

        return rule


class ViewCaseRuleView(EditCaseRuleView):
    urlname = 'view_case_rule'
    page_title = gettext_lazy("View Case Rule")

    @property
    @memoized
    def read_only_mode(self):
        return True


@method_decorator(requires_privilege_with_fallback(privileges.CASE_DEDUPE), name='dispatch')
class DeduplicationRuleListView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = 'data_interfaces/list_deduplication_rules.html'
    urlname = 'deduplication_rules'
    page_title = gettext_lazy("Deduplicate Cases")

    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'

    rule_workflow = AutomaticUpdateRule.WORKFLOW_DEDUPLICATE

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    @property
    def page_context(self):
        context = self.pagination_context
        domain_obj = Domain.get_by_name(self.domain)
        hour = domain_obj.auto_case_update_hour
        context.update({
            'help_site_url': 'https://confluence.dimagi.com/display/commcarepublic/Automatically+Close+Cases',
            'time': f"{hour}:00" if hour else _('midnight'),  # noqa: E999
        })
        return context

    @property
    def paginated_list(self):
        for rule in self._rules()[self.skip:self.skip + self.limit]:
            yield {
                'itemData': self._format_rule(rule),
                'template': 'base-rule-template',
            }

    @property
    def total(self):
        return self._rules().count()

    @memoized
    def _rules(self):
        return AutomaticUpdateRule.by_domain(
            self.domain,
            self.rule_workflow,
            active_only=False,
        ).order_by('name', 'id')

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Case Type"),
            _("Status"),
            _("Potential Duplicate Count"),
            _("Action"),
        ]

    @property
    def edit_url_name(self):
        return DeduplicationRuleEditView.urlname

    @property
    def allowed_actions(self):
        actions = super().allowed_actions
        actions.append(self.ACTION_ACTIVATE)
        actions.append(self.ACTION_DEACTIVATE)
        return actions

    @property
    def activate_response(self):
        return self.update_rule()

    @property
    def deactivate_response(self):
        return self.update_rule()

    def get_deleted_item_data(self, rule_id):
        (rule, error) = self._get_rule(rule_id)
        if rule is None:
            return {'success': False, 'error': error}

        rule.soft_delete()

        return {
            'itemData': {
                'name': rule.name,
            },
            'template': 'rule-deleted-template',
        }

    def update_rule(self):
        (rule, error) = self._get_rule(self.parameters.get('id'))
        if rule is None:
            return {'success': False, 'error': error}

        if self.action == self.ACTION_ACTIVATE:
            rule.activate()
        elif self.action == self.ACTION_DEACTIVATE:
            rule.activate(False)

        return {'success': True, 'itemData': self._format_rule(rule)}

    def _get_rule(self, rule_id):
        if rule_id is None:
            return None, _("Please provide an id.")

        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id, workflow=self.rule_workflow)
        except AutomaticUpdateRule.DoesNotExist:
            return None, _("Rule not found.")

        if rule.domain != self.domain:
            return None, _("Rule not found.")

        return rule, None

    def _format_rule(self, rule):
        ret = {
            'id': rule.pk,
            'name': rule.name,
            'case_type': rule.case_type,
            'is_case_type_deprecated': is_case_type_deprecated(self.domain, rule.case_type),
            'active': rule.active,
            'last_run': (ServerTime(rule.last_run)
                         .user_time(get_timezone_for_user(None, self.domain))
                         .done()
                         .strftime(SERVER_DATETIME_FORMAT)) if rule.last_run else '-',
            'edit_url': reverse(self.edit_url_name, args=[self.domain, rule.pk]),
            'action_error': "",     # must be provided because knockout template looks for it
        }
        case_list_explorer_case_props = list(col["name"] for col in CaseListExplorerColumns.DEFAULT_COLUMNS)
        rule_properties = (
            set(CaseDeduplicationActionDefinition.from_rule(rule).case_properties)
            - set(case_list_explorer_case_props)
        )
        ret['duplicates_count'] = self._get_duplicates_count(rule)
        ret['explore_url'] = reverse_with_params(
            'project_report_dispatcher',
            args=(self.domain, 'duplicate_cases'),
            params={
                "duplicate_case_rule": rule.id,
                "explorer_columns": json.dumps(case_list_explorer_case_props + list(rule_properties)),
            },
        )

        return ret

    def _get_duplicates_count(self, rule):
        if rule.locked_for_editing:
            progress_helper = MessagingRuleProgressHelper(rule.id)
            return _("Processing - {progress_percent}% ({cases_processed}/{total_cases} cases) complete").format(
                progress_percent=progress_helper.get_progress_pct(),
                cases_processed=progress_helper.get_cases_processed(),
                total_cases=progress_helper.get_total_cases_to_process(),
            )
        action = CaseDeduplicationActionDefinition.from_rule(rule)
        return CaseDuplicateNew.objects.filter(action=action).count()


@method_decorator(requires_privilege_with_fallback(privileges.CASE_DEDUPE), name='dispatch')
class DeduplicationRuleCreateView(DataInterfaceSection):
    template_name = "data_interfaces/edit_deduplication_rule.html"
    urlname = 'add_deduplication_rule'
    page_title = gettext_lazy("Create Deduplication Rule")

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            'all_case_properties': self.get_augmented_data_dict_props_by_case_type(self.domain),
            'case_types': sorted(list(get_case_types_for_domain(self.domain))),
            'criteria_form': self.case_filter_form,
            'update_actions_enabled': toggles.CASE_DEDUPE_UPDATES.enabled(self.domain),
        })
        return context

    @classmethod
    def get_augmented_data_dict_props_by_case_type(cls, domain):
        return {
            t: sorted(names.union({const.CASE_UI_NAME, const.CASE_UI_OWNER_ID})) for t, names in
            get_data_dict_props_by_case_type(domain).items()
        }

    def get_context_data(self, **kwargs):
        context = super(DeduplicationRuleCreateView, self).get_context_data(**kwargs)
        if 'error' in kwargs and kwargs['error']:
            rule = kwargs['rule_params']
            action = kwargs['action_params']
            context.update(
                {
                    "name": rule['name'],
                    "case_type": rule['case_type'],
                    "match_type": action['match_type'],
                    "case_properties": action['case_properties'],
                    "include_closed": action['include_closed'],
                    "properties_to_update": [
                        {"name": prop["name"], "valueType": prop["value_type"], "value": prop["value"]}
                        for prop in action['properties_to_update']
                    ],
                }
            )
        return context

    def post(self, request, *args, **kwargs):
        rule_params, action_params = self.parse_params(request)
        errors = self.validate_action_params(action_params)
        errors.extend(self.validate_rule_params(request.domain, rule_params))

        cases_filter_form = DedupeCaseFilterForm(request.domain, request.POST)

        if not cases_filter_form.is_valid():
            errors.extend(cases_filter_form.errors)

        if errors:
            messages.error(
                request, _('Deduplication rule not saved due to the following issues: %s') %
                '<ul><li>{}</li></ul>'.format('</li><li>'.join(errors)),
                extra_tags='html'
            )

            kwargs.update({
                'error': True,
                'rule_params': rule_params,
                'action_params': action_params,
            })
            return self.get(request, *args, **kwargs)

        with transaction.atomic():
            rule = self._create_rule(request.domain, **rule_params)
            _action, _action_definition = rule.add_action(
                CaseDeduplicationActionDefinition,
                **action_params
            )
            cases_filter_form.save_criteria(rule, save_meta=False)

        reset_and_backfill_deduplicate_rule(rule)
        messages.success(request, _("Successfully created deduplication rule: {}").format(rule.name))
        self._track_rule_created(request.couch_user.username, rule, _action_definition)

        return HttpResponseRedirect(
            reverse(DeduplicationRuleEditView.urlname, kwargs={"domain": self.domain, "rule_id": rule.id})
        )

    def _track_rule_created(self, username, rule, action_definition):
        from corehq.apps.accounting.models import Subscription, SubscriptionType
        subscription = Subscription.get_active_subscription_by_domain(rule.domain)
        managed_by_saas = bool(subscription and subscription.service_type == SubscriptionType.PRODUCT)

        track_workflow(
            username,
            'Created Dedupe Rule',
            {
                'domain': self.domain,
                'num_properties': len(action_definition.case_properties),
                'managed_by_saas': managed_by_saas,
            }
        )

    @property
    def case_filter_form(self):
        return DedupeCaseFilterForm(
            self.domain,
            rule=None,
            couch_user=self.request.couch_user,
        )

    def parse_params(self, request):
        rule_params = {
            "name": request.POST.get("name"),
            "case_type": request.POST.get("case_type"),
        }
        action_params = {
            "match_type": request.POST.get("match_type"),
            "case_properties": [
                prop['name'].strip()
                for prop in json.loads(request.POST.get("case_properties"))
                if prop
            ],
            "include_closed": request.POST.get("include_closed") == "on",
        }
        if toggles.CASE_DEDUPE_UPDATES.enabled(self.domain):
            properties_to_update = [
                {"name": prop["name"], "value_type": prop["valueType"], "value": prop["value"]}
                for prop in json.loads(request.POST.get("properties_to_update"))
            ]
        else:
            properties_to_update = []

        action_params["properties_to_update"] = properties_to_update

        return rule_params, action_params

    def validate_rule_params(self, domain, rule_params, rule=None):
        existing_rule = AutomaticUpdateRule.objects.filter(
            deleted=False,
            domain=domain,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            name=rule_params['name'],
        )
        if existing_rule and existing_rule[0] != rule:
            return [_("A rule with name {name} already exists").format(name=rule_params['name'])]
        return []

    def validate_action_params(self, action_params):
        errors = []
        case_properties = action_params['case_properties']
        if len(set(case_properties)) != len(case_properties):
            errors.append(_("Matching case properties must be unique"))

        update_properties = [prop['name'] for prop in action_params['properties_to_update']]
        update_properties_set = set(update_properties)
        reserved_properties = set(prop.replace("@", "") for prop in SPECIAL_CASE_PROPERTIES)
        reserved_properties.add(CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME)

        reserved_properties_updated = (
            reserved_properties & update_properties_set
        )
        if reserved_properties_updated:
            errors.append(
                _("You cannot update reserved property: {}").format(
                    ",".join(reserved_properties_updated))
            )
        if len(update_properties_set) != len(update_properties):
            errors.append(_("Action case properties must be unique"))

        if set(case_properties) & update_properties_set:
            errors.append(_("You cannot update properties that are used to match a duplicate."))
        return errors

    def _create_rule(self, domain, name, case_type):
        return AutomaticUpdateRule.objects.create(
            domain=domain,
            name=name,
            case_type=case_type,
            active=False,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )


@method_decorator(requires_privilege_with_fallback(privileges.CASE_DEDUPE), name='dispatch')
class DeduplicationRuleEditView(DeduplicationRuleCreateView):
    urlname = 'edit_deduplication_rule'
    page_title = gettext_lazy("Edit Deduplication Rule")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.rule_id])

    @property
    def rule_id(self):
        return self.kwargs.get('rule_id')

    @property
    @memoized
    def rule(self):
        return get_object_or_404(
            AutomaticUpdateRule,
            id=self.rule_id,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            domain=self.domain,
            deleted=False,
        )

    @property
    @memoized
    def dedupe_action(self):
        return CaseDeduplicationActionDefinition.from_rule(self.rule)

    @property
    def page_context(self):
        context = super().page_context
        context.update({
            "name": self.rule.name,
            "case_type": self.rule.case_type,
            "match_type": self.dedupe_action.match_type,
            "case_properties": self.dedupe_action.case_properties,
            "include_closed": self.dedupe_action.include_closed,
            "properties_to_update": [
                {"name": prop["name"], "valueType": prop["value_type"], "value": prop["value"]}
                for prop in self.dedupe_action.properties_to_update
            ],
            "readonly": self.rule.locked_for_editing,
            "criteria_form": self.case_filter_form,
        })

        if self.rule.locked_for_editing:
            progress_helper = MessagingRuleProgressHelper(self.rule_id)
            context.update({
                "progress": progress_helper.get_progress_pct(),
                "complete": progress_helper.get_cases_processed(),
                "total": progress_helper.get_total_cases_to_process(),
            })
        return context

    def post(self, request, *args, **kwargs):
        if self.rule.locked_for_editing:
            messages.error(
                request,
                _("Rule {name} is currently backfilling and cannot be edited").format(name=self.rule.name)
            )
            return HttpResponseRedirect(
                reverse(DeduplicationRuleEditView.urlname, kwargs={
                    "domain": self.domain,
                    "rule_id": self.rule.id
                })
            )

        rule_params, action_params = self.parse_params(request)
        errors = self.validate_action_params(action_params)
        errors.extend(self.validate_rule_params(request.domain, rule_params, self.rule))

        cases_filter_form = DedupeCaseFilterForm(request.domain, request.POST)

        if not cases_filter_form.is_valid():
            errors.extend(cases_filter_form.errors)

        if errors:
            messages.error(
                request, _('Deduplication rule not saved due to the following issues: %s') %
                '<ul><li>{}</li></ul>'.format('</li><li>'.join(errors)),
                extra_tags='html'
            )

            kwargs.update({
                'error': True,
                'rule_params': rule_params,
                'action_params': action_params,
            })
            return self.get(request, *args, **kwargs)

        filter_criteria_updated = False

        with transaction.atomic():
            rule_modified = self._update_model_instance(self.rule, rule_params)
            action_modified = self._update_model_instance(self.dedupe_action, action_params)

            # Is there a good way to check if the criteria has changed without
            # going over each and every value?
            cases_filter_form.save_criteria(self.rule, save_meta=False)
            filter_criteria_updated = True

        if rule_modified or action_modified or filter_criteria_updated:
            reset_and_backfill_deduplicate_rule(self.rule)
            messages.success(
                request,
                _('Rule {name} was updated, and has been queued for backfilling').format(name=self.rule.name)
            )
        else:
            messages.info(
                request,
                _('Rule {name} was not updated, since nothing changed').format(name=self.rule.name)
            )

        return HttpResponseRedirect(
            reverse(DeduplicationRuleEditView.urlname, kwargs={
                "domain": self.domain,
                "rule_id": self.rule.id
            })
        )

    @property
    def case_filter_form(self):
        return DedupeCaseFilterForm(
            self.domain,
            rule=self.rule,
            couch_user=self.request.couch_user,
        )

    def _update_model_instance(self, model, params):
        to_save = False
        for key, value in params.items():
            if getattr(model, key) != value:
                setattr(model, key, value)
                to_save = True
        if to_save:
            model.save()

        return to_save
