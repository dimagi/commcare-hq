from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import csv342 as csv
import io
import json
import uuid

import six
from couchdbkit import ResourceNotFound
from django.contrib import messages
from django.core.cache import cache
from django.views.decorators.http import require_GET

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.casegroups.dbaccessors import get_case_groups_in_domain, \
    get_number_of_case_groups_in_domain
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqwebapp.models import PageInfoContext
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.dbaccessors import user_ids_at_accessible_locations

from corehq.apps.reports.v2.reports.explore_case_data import (
    ExploreCaseDataReport,
)
from corehq.apps.users.permissions import can_download_data_files
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from django.utils.decorators import method_decorator
from corehq.apps.data_interfaces.tasks import bulk_upload_cases_to_group, bulk_form_management_async
from corehq.apps.data_interfaces.forms import (
    AddCaseGroupForm, UpdateCaseGroupForm, AddCaseToGroupForm,
    CaseUpdateRuleForm, CaseRuleCriteriaForm,
    CaseRuleActionsForm)
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqcase.utils import get_case_by_identifier
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin, PaginatedItemException
from corehq.apps.data_interfaces.dispatcher import (
    EditDataInterfaceDispatcher,
    require_can_edit_data,
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.sms.views import BaseMessagingSectionView
from corehq.const import SERVER_DATETIME_FORMAT
from .dispatcher import require_form_management_privilege
from .interfaces import FormManagementMode, BulkFormManagementInterface
from django.db import transaction
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseServerError, HttpResponseBadRequest
from django.shortcuts import render
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from memoized import memoized
from no_exceptions.exceptions import Http403
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context
from six.moves import map


@login_and_domain_required
@location_safe
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()

    return HttpResponseRedirect(default_data_view_url(request, domain))


def default_data_view_url(request, domain):
    from corehq.apps.export.views.list import (
        CaseExportListView,
        FormExportListView,
        DeIdFormExportListView,
    )
    from corehq.apps.export.views.utils import (DataFileDownloadList, user_can_view_deid_exports,
        can_view_form_exports, can_view_case_exports)
    from corehq.apps.data_interfaces.interfaces import CaseReassignmentInterface

    if can_view_form_exports(request.couch_user, domain):
        return reverse(FormExportListView.urlname, args=[domain])
    elif can_view_case_exports(request.couch_user, domain):
        return reverse(CaseExportListView.urlname, args=[domain])

    if user_can_view_deid_exports(domain, request.couch_user):
        return reverse(DeIdFormExportListView.urlname, args=[domain])

    if can_download_data_files(domain, request.couch_user):
        return reverse(DataFileDownloadList.urlname, args=[domain])

    if request.couch_user.can_edit_data:
        return CaseReassignmentInterface.get_url(domain)

    raise Http404()


class BulkUploadCasesException(Exception):
    pass


class DataInterfaceSection(BaseDomainView):
    section_name = ugettext_noop("Data")
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
    page_title = ugettext_lazy("Explore Case Data")

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
            messages.error(self.request, six.text_type(e))
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
            raise BulkUploadCasesException(six.text_type(e))

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
    page_title = ugettext_noop('Form Management')

    def post(self, request, *args, **kwargs):
        form_ids = self.get_xform_ids(request)
        if not self.request.can_access_all_locations:
            inaccessible_forms_accessed = self.inaccessible_forms_accessed(
                form_ids, self.domain, request.couch_user)
            if inaccessible_forms_accessed:
                return HttpResponseBadRequest(
                    "Inaccessible forms accessed. Id(s): %s " % ','.join(inaccessible_forms_accessed))

        mode = self.request.POST.get('mode')
        task_ref = expose_cached_download(payload=None, expiry=1*60*60, file_extension=None)
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
        xforms = FormAccessors(domain).get_forms(xform_ids)
        xforms_user_ids = set([xform.user_id for xform in xforms])
        accessible_user_ids = set(user_ids_at_accessible_locations(domain, couch_user))
        return xforms_user_ids - accessible_user_ids

    def get_xform_ids(self, request):
        if 'select_all' in self.request.POST:
            # Altough evaluating form_ids and sending to task would be cleaner,
            # heavier calls should be in an async task instead
            import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
            form_query_string = six.moves.urllib.parse.unquote(self.request.POST.get('select_all'))
            from django.http import HttpRequest, QueryDict
            from django_otp.middleware import OTPMiddleware

            _request = HttpRequest()
            _request.couch_user = request.couch_user
            _request.user = request.couch_user.get_django_user()
            _request.domain = self.domain
            _request.couch_user.current_domain = self.domain
            _request.can_access_all_locations = request.couch_user.has_permission(self.domain,
                                                                                  'access_all_locations')
            _request.session = request.session

            _request.GET = QueryDict(form_query_string)
            OTPMiddleware().process_request(_request)

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
        return render(request, 'hqwebapp/soil_status_full.html', context)

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


@login_and_domain_required
@require_GET
def find_by_id(request, domain):
    from corehq.apps.export.views.utils import can_view_form_exports, can_view_case_exports
    can_view_cases = can_view_case_exports(request.couch_user, domain)
    can_view_forms = can_view_form_exports(request.couch_user, domain)

    if not can_view_cases and not can_view_forms:
        raise Http403()

    name = _("Find Case or Form Submission by ID")
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



class AutomaticUpdateRuleListView(DataInterfaceSection, CRUDPaginatedViewMixin):
    template_name = 'data_interfaces/list_automatic_update_rules.html'
    urlname = 'automatic_update_rule_list'
    page_title = ugettext_lazy("Automatically Close Cases")

    limit_text = ugettext_lazy("rules per page")
    empty_notification = ugettext_lazy("You have no case rules.")
    loading_message = ugettext_lazy("Loading rules...")
    deleted_items_header = ugettext_lazy("Deleted Rules")

    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'

    @method_decorator(requires_privilege_with_fallback(privileges.DATA_CLEANUP))
    def dispatch(self, *args, **kwargs):
        return super(AutomaticUpdateRuleListView, self).dispatch(*args, **kwargs)

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def allowed_actions(self):
        actions = super(AutomaticUpdateRuleListView, self).allowed_actions
        actions.append(self.ACTION_ACTIVATE)
        actions.append(self.ACTION_DEACTIVATE)
        return actions

    @property
    def page_context(self):
        context = self.pagination_context
        context['help_site_url'] = 'https://confluence.dimagi.com/display/commcarepublic/Automatically+Close+Cases'
        return context

    @property
    def total(self):
        return self._rules().count()

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Case Type"),
            _("Status"),
            _("Last Run"),
            _("Action"),
        ]

    @property
    @memoized
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

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
            'edit_url': reverse(EditCaseRuleView.urlname, args=[self.domain, rule.pk]),
            'action_error': "",     # must be provided because knockout template looks for it
        }

    @property
    def paginated_list(self):
        for rule in self._rules()[self.skip:self.skip + self.limit]:
            yield {
                'itemData': self._format_rule(rule),
                'template': 'base-rule-template',
            }

    @memoized
    def _rules(self):
        return AutomaticUpdateRule.by_domain(
            self.domain,
            AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            active_only=False,
        ).order_by('name', 'id')

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def _get_rule(self, rule_id):
        if rule_id is None:
            return None, _("Please provide an id.")

        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id, workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        except AutomaticUpdateRule.DoesNotExist:
            return None, _("Rule not found.")

        if rule.domain != self.domain:
            return None, _("Rule not found.")

        return rule, None

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

    @property
    def activate_response(self):
        return self.update_rule()

    @property
    def deactivate_response(self):
        return self.update_rule()


class AddCaseRuleView(DataInterfaceSection):
    template_name = "data_interfaces/case_rule.html"
    urlname = 'add_case_rule'
    page_title = ugettext_lazy("Add Case Rule")

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
        return (
            not self.is_system_admin and
            (
                self.criteria_form.requires_system_admin_to_edit or
                self.actions_form.requires_system_admin_to_edit
            )
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
                self.criteria_form.requires_system_admin_to_save or
                self.actions_form.requires_system_admin_to_save
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
    page_title = ugettext_lazy("Edit Case Rule")

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
            rule = AutomaticUpdateRule.objects.get(pk=self.rule_id,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        except AutomaticUpdateRule.DoesNotExist:
            raise Http404()

        if rule.domain != self.domain or rule.deleted:
            raise Http404()

        return rule
