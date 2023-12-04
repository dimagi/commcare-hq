import copy
import csv
import io
import re
from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET, require_POST

from django_prbac.utils import has_privilege
from memoized import memoized

from casexml.apps.case import const
from casexml.apps.case.cleanup import close_case, rebuild_case_from_forms
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.util import (
    get_case_history,
    get_paged_changes_to_case_property,
)
from casexml.apps.case.views import get_wrapped_case
from casexml.apps.case.xml import V2
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from dimagi.utils.chunked import chunked
from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import get_latest_app_ids_and_versions, get_app
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.data_dictionary.util import is_case_type_deprecated
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.export.const import KNOWN_CASE_PROPERTIES
from corehq.apps.export.models import CaseExportDataSchema
from corehq.apps.export.utils import is_occurrence_deleted
from corehq.apps.hqcase.utils import (
    EDIT_FORM_XMLNS,
    resave_case,
    submit_case_blocks,
)
from corehq.apps.hqwebapp.decorators import use_datatables
from corehq.apps.hqwebapp.templatetags.proptable_tags import (
    DisplayConfig,
    get_table_as_rows,
)
from corehq.apps.locations.permissions import (
    location_restricted_exception,
    location_safe,
    user_can_access_case,
)
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.view_helpers import case_hierarchy_context
from corehq.apps.reports.views import (
    archive_form,
    DATE_FORMAT,
    BaseProjectReportSectionView,
    get_data_cleaning_updates,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import (
    CommCareCase,
    UserRequestedRebuild,
    XFormInstance,
)
from corehq.motech.repeaters.dbaccessors import (
    get_repeat_records_by_payload_id,
)
from corehq.motech.repeaters.views.repeat_record_display import (
    RepeatRecordDisplay,
)
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.view_utils import absolute_reverse, get_case_or_404, reverse

from .basic import CaseListReport
from .utils import get_user_type

# Number of columns in case property history popup
DYNAMIC_CASE_PROPERTIES_COLUMNS = 4


require_case_view_permission = require_permission(
    HqPermissions.view_report,
    'corehq.apps.reports.standard.cases.basic.CaseListReport',
    login_decorator=None,
)


def can_view_attachments(request):
    return (
        request.couch_user.has_permission(
            request.domain, 'view_report',
            data='corehq.apps.reports.standard.cases.basic.CaseListReport'
        )
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.user.username)
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.domain)
    )


def safely_get_case(request, domain, case_id):
    """Get case if accessible else raise a 404 or 403"""
    case = get_case_or_404(domain, case_id)
    if not (request.can_access_all_locations
            or user_can_access_case(domain, request.couch_user, case)):
        raise location_restricted_exception(request)
    return case


@location_safe
class CaseDataView(BaseProjectReportSectionView):
    urlname = 'case_data'
    template_name = "reports/reportdata/case_data.html"
    page_title = gettext_lazy("Case Data")
    http_method_names = ['get']

    @method_decorator(require_case_view_permission)
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if not self.case_instance:
            messages.info(request,
                          _("Sorry, we couldn't find that case. If you think this "
                            "is a mistake please report an issue."))
            return HttpResponseRedirect(CaseListReport.get_url(domain=self.domain))
        if not (request.can_access_all_locations
                or user_can_access_case(self.domain, self.request.couch_user, self.case_instance)):
            raise location_restricted_exception(request)
        return super(CaseDataView, self).dispatch(request, *args, **kwargs)

    @property
    def case_id(self):
        return self.kwargs['case_id']

    @property
    @memoized
    def case_instance(self):
        try:
            case = CommCareCase.objects.get_case(self.case_id, self.domain)
            if case.domain != self.domain or case.is_deleted:
                return None
            return case
        except CaseNotFound:
            return None

    @property
    def page_name(self):
        return case_inline_display(self.case_instance)

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.case_id,))

    @property
    def parent_pages(self):
        return [{
            'title': CaseListReport.name,
            'url': CaseListReport.get_url(domain=self.domain),
        }]

    @property
    def page_context(self):
        opening_transactions = self.case_instance.get_opening_transactions()
        if not opening_transactions:
            messages.error(self.request, _(
                "The case creation form could not be found. "
                "Usually this happens if the form that created the case is archived "
                "but there are other forms that updated the case. "
                "To fix this you can archive the other forms listed here."
            ))

        wrapped_case = get_wrapped_case(self.case_instance)
        timezone = get_timezone_for_user(self.request.couch_user, self.domain)
        # Get correct timezone for the current date: https://github.com/dimagi/commcare-hq/pull/5324
        timezone = timezone.localize(datetime.utcnow()).tzinfo
        show_transaction_export = toggles.COMMTRACK.enabled(self.request.user.username)

        def _get_case_url(case_id):
            return absolute_reverse(self.urlname, args=[self.domain, case_id])

        data = copy.deepcopy(wrapped_case.to_full_dict())
        display = wrapped_case.get_display_config()
        default_properties = get_table_as_rows(data, display, timezone)
        dynamic_data = wrapped_case.dynamic_properties()

        for row in display['layout']:
            for item in row:
                dynamic_data.pop(item.expr, None)

        product_name_by_id = {
            product['product_id']: product['name']
            for product in SQLProduct.objects.filter(domain=self.domain).values('product_id', 'name').all()
        }

        def _product_name(product_id):
            return product_name_by_id.get(product_id, _('Unknown Product ("{}")').format(product_id))

        ledger_map = LedgerAccessors(self.domain).get_case_ledger_state(self.case_id, ensure_form_id=True)
        for section, entry_map in ledger_map.items():
            product_tuples = [
                (_product_name(product_id), entry_map[product_id])
                for product_id in entry_map
            ]
            product_tuples.sort(key=lambda x: x[0])
            ledger_map[section] = product_tuples

        repeat_records = [
            RepeatRecordDisplay(record, timezone, date_format=DATE_FORMAT)
            for record in get_repeat_records_by_payload_id(self.domain, self.case_id)
        ]

        can_edit_data = self.request.couch_user.can_edit_data
        show_properties_edit = (
            can_edit_data
            and has_privilege(self.request, privileges.DATA_CLEANUP)
        )

        context = {
            "case_id": self.case_id,
            "case": self.case_instance,
            "show_case_rebuild": toggles.SUPPORT.enabled(self.request.user.username),
            "can_edit_data": can_edit_data,
            "is_usercase": self.case_instance.type == USERCASE_TYPE,
            "is_case_type_deprecated": is_case_type_deprecated(self.domain, self.case_instance.type),

            "default_properties_as_table": default_properties,
            "dynamic_properties": dynamic_data,
            "show_properties_edit": show_properties_edit,
            "timezone": timezone,
            "tz_abbrev": timezone.zone,
            "ledgers": ledger_map,
            "show_transaction_export": show_transaction_export,
            "xform_api_url": reverse('single_case_forms', args=[self.domain, self.case_id]),
            "repeat_records": repeat_records,
        }
        if dynamic_data:
            case_property_tables = _get_case_property_tables(
                self.domain, self.case_instance.type, dynamic_data, timezone)
            context['case_property_tables'] = case_property_tables
            context['show_expand_collapse_buttons'] = len(
                [table.get('name') for table in case_property_tables if table.get('name') is not None]) > 1
        context.update(case_hierarchy_context(self.case_instance, _get_case_url, timezone=timezone))
        return context


def _get_case_property_tables(domain, case_type, dynamic_data, timezone):
    if domain_has_privilege(domain, privileges.DATA_DICTIONARY):
        dd_props_by_group = list(_get_dd_props_by_group(domain, case_type))
    else:
        dd_props_by_group = []
    tables = [
        (group, _table_definition([
            (p.name, p.label, p.description) for p in props
        ]))
        for group, props in dd_props_by_group
    ]
    props_in_dd = set(prop.name for _, prop_group in dd_props_by_group
                      for prop in prop_group)
    unrecognized = set(dynamic_data.keys()) - props_in_dd - {'case_name'}
    if unrecognized:
        header = _('Unrecognized') if tables else None
        tables.append((header, _table_definition([
            (p, None, None) for p in unrecognized
        ])))

    return [{
        'name': name,
        'rows': get_table_as_rows(dynamic_data, definition, timezone),
    } for name, definition in tables]


def _get_dd_props_by_group(domain, case_type):
    ret = defaultdict(list)
    for prop in CaseProperty.objects.filter(
            case_type__domain=domain,
            case_type__name=case_type,
            deprecated=False,
    ).select_related('group').order_by('group__index', 'index'):
        ret[prop.group_name or None].append(prop)

    uncategorized = ret.pop(None, None)
    for group, props in ret.items():
        yield group, props

    if uncategorized:
        yield _('Uncategorized') if ret else None, uncategorized


def _table_definition(props):
    return {
        "layout": list(chunked([
            DisplayConfig(
                expr=prop_name,
                name=_add_line_break_opportunities(label or prop_name),
                description=description,
                has_history=True
            ) for prop_name, label, description in props
        ], DYNAMIC_CASE_PROPERTIES_COLUMNS))
    }


def _add_line_break_opportunities(name):
    # Add zero-width space after dashes and underscores for better looking word breaks
    return re.sub(r"([_-])", "\\1\u200B", name)


def form_to_json(domain, form, timezone):
    form_name = xmlns_to_name(
        domain,
        form.xmlns,
        app_id=form.app_id,
        lang=get_language(),
        form_name=form.form_data.get('@name')
    )
    received_on = ServerTime(form.received_on).user_time(timezone).done().strftime(DATE_FORMAT)

    return {
        'id': form.form_id,
        'received_on': received_on,
        'user': {
            "id": form.user_id or '',
            "username": form.metadata.username if form.metadata else '',
        },
        'readable_name': form_name,
        'user_type': get_user_type(form, domain),
    }


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_forms(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    try:
        start_range = int(request.GET['start_range'])
        end_range = int(request.GET['end_range'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    slice = list(reversed(case.xform_ids))[start_range:end_range]
    forms = XFormInstance.objects.get_forms(slice, domain, ordered=True)
    timezone = get_timezone_for_user(request.couch_user, domain)
    return json_response([
        form_to_json(domain, form, timezone) for form in forms
    ])


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_property_changes(request, domain, case_id, case_property_name):
    """Returns all changes to a case property
    """
    case = safely_get_case(request, domain, case_id)
    timezone = get_timezone_for_user(request.couch_user, domain)
    next_transaction = int(request.GET.get('next_transaction', 0))

    paged_changes, last_transaction_checked = get_paged_changes_to_case_property(
        case,
        case_property_name,
        start=next_transaction,
    )

    changes = []
    for change in paged_changes:
        change_json = form_to_json(domain, change.transaction.form, timezone)
        change_json['new_value'] = change.new_value
        change_json['form_url'] = reverse('render_form_data', args=[domain, change.transaction.form.form_id])
        changes.append(change_json)

    return json_response({
        'changes': changes,
        'last_transaction_checked': last_transaction_checked,
    })


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def download_case_history(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    track_workflow(request.couch_user.username, "Case Data Page: Case History csv Downloaded")
    history = get_case_history(case)
    properties = set()
    for f in history:
        properties |= set(f.keys())
    properties = sorted(list(properties))
    columns = [properties]
    for f in history:
        columns.append([f.get(prop, '') for prop in properties])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="case_history_{}.csv"'.format(case.name)

    writer = csv.writer(response)
    writer.writerows(zip(*columns))   # transpose the columns to rows
    return response


@location_safe
class CaseAttachmentsView(CaseDataView):
    urlname = 'single_case_attachments'
    template_name = "reports/reportdata/case_attachments.html"
    page_title = gettext_lazy("Case Attachments")
    http_method_names = ['get']

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not can_view_attachments(request):
            return HttpResponseForbidden(_("You don't have permission to access this page."))
        return super(CaseAttachmentsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return "{} '{}'".format(
            _("Attachments for case"), super(CaseAttachmentsView, self).page_name
        )


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_xml(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    version = request.GET.get('version', V2)
    return HttpResponse(case.to_xml(version), content_type='text/xml')


@location_safe
@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_GET
def case_property_names(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)

    # We need to look at the export schema in order to remove any case properties that
    # have been deleted from the app. When the data dictionary is fully public, we can use that
    # so that users may deprecate those properties manually
    export_schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case.type)
    property_schema = export_schema.group_schemas[0]
    last_app_ids = get_latest_app_ids_and_versions(domain)
    all_property_names = {
        item.path[-1].name for item in property_schema.items
        if not is_occurrence_deleted(item.last_occurrences, last_app_ids) and '/' not in item.path[-1].name
    }
    all_property_names = all_property_names.difference(KNOWN_CASE_PROPERTIES) | {"case_name"}
    # external_id is effectively a dynamic property: see CaseDisplayWrapper.dynamic_properties
    if case.external_id:
        all_property_names.add('external_id')

    return json_response(sorted(all_property_names, key=lambda item: item.lower()))


@location_safe
@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
def edit_case_view(request, domain, case_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    case = safely_get_case(request, domain, case_id)
    user = request.couch_user

    old_properties = case.dynamic_case_properties()
    old_properties['external_id'] = None    # special handling below
    updates = get_data_cleaning_updates(request, old_properties)

    case_block_kwargs = {}

    # User may also update external_id; see CaseDisplayWrapper.dynamic_properties
    if 'external_id' in updates:
        if updates['external_id'] != case.external_id:
            case_block_kwargs['external_id'] = updates['external_id']
        updates.pop('external_id')

    if updates:
        case_block_kwargs['update'] = updates

    if case_block_kwargs:
        submit_case_blocks([CaseBlock(case_id=case_id, **case_block_kwargs).as_text()],
            domain, username=user.username, user_id=user._id, device_id=__name__ + ".edit_case",
            xmlns=EDIT_FORM_XMLNS)
        messages.success(request, _('Case properties saved for %s.' % case.name))
    else:
        messages.success(request, _('No changes made to %s.' % case.name))
    return JsonResponse({'success': 1})


@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
def rebuild_case_view(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(user_id=request.couch_user.user_id))
    messages.success(request, _('Case %s was rebuilt from its forms.' % case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
def resave_case_view(request, domain, case_id):
    """Re-save the case to have it re-processed by pillows
    """
    case = get_case_or_404(domain, case_id)
    resave_case(domain, case)
    messages.success(
        request,
        _('Case %s was successfully saved. Hopefully it will show up in all reports momentarily.' % case.name),
    )
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@location_safe
@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
def close_case_view(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    if case.closed:
        messages.info(request, 'Case {} is already closed.'.format(case.name))
    else:
        device_id = __name__ + ".close_case_view"
        form_id = close_case(case_id, domain, request.couch_user, device_id)
        msg = format_html(
            _('''Case {name} has been closed.
            <a href="{url}" class="post-link">Undo</a>.
            You can also reopen the case in the future by archiving the last form in the case history.
        '''),
            name=case.name,
            url=reverse('undo_close_case', args=[domain, case_id, form_id]),
        )
        messages.success(request, msg, extra_tags='html')
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


MAX_CASE_COUNT = 10
MAX_SUBCASE_DEPTH = 3


@location_safe
def get_cases_and_forms_for_deletion(request, domain, case_id):
    delete_cases = []  # list of cases to be soft deleted
    delete_forms = []  # list of forms to be soft deleted

    # For formatting the list of cases/submission forms
    cases = {}  # structured like: {case: {form: {case touched by form: actions taken by form}}}
    case_names = {}  # {case_id: case_name}
    form_names = {}  # {form_ids: form name}
    reopened_cases = {}
    affected_cases = {}

    update_actions = [const.CASE_ACTION_INDEX,
                      const.CASE_ACTION_UPDATE,
                      const.CASE_ACTION_ATTACHMENT,
                      const.CASE_ACTION_COMMTRACK,
                      const.CASE_ACTION_REBUILD]

    def get_forms_for_deletion_from_case(case, subcase_count):
        delete_cases.append(case.case_id)
        if len(delete_cases) > MAX_CASE_COUNT or subcase_count >= MAX_SUBCASE_DEPTH:
            raise ValueError("Too many cases to delete")
        if case.case_id not in cases:
            cases[case.case_id] = {}
            case_names[case.case_id] = case.name
            if len(case_names) == 1:  # only add primary label to first/main case
                case_names[case.case_id] += ' <span class="label label-default">primary case</span>'
        case_xforms = case.xform_ids

        for form_id in case_xforms:
            if form_id not in delete_forms:
                delete_forms.insert(0, form_id)
            form_object = XFormInstance.objects.get_form(form_id, domain)
            if form_id not in form_names:
                form_names[form_id] = xmlns_to_name(domain, form_object.xmlns, form_object.app_id)
                if form_names[form_id] == form_object.xmlns:
                    form_name = [
                        get_app(domain, form_object.app_id).name or "[Unknown App]",
                        "[Unknown Module]",
                        form_object.name or "[Unknown Form]"
                    ]
                    form_names[form_id] = ' > '.join(form_name)
            case_db = FormProcessorInterface(domain).casedb_cache(
                domain=domain,
                load_src="process_stock",
            )
            touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, [form_object])

            case_actions = {}
            for touched_id in touched_cases:
                case_object = safely_get_case(request, domain, touched_id)
                actions = list(touched_cases[touched_id].actions)
                if touched_id == case.case_id:
                    case_actions['current'] = actions
                elif touched_id not in delete_cases:
                    if touched_id not in case_actions:
                        case_actions[case_object.name] = actions
                    if const.CASE_ACTION_CREATE in actions and touched_id != case.case_id:
                        subcase_count += 1
                        get_forms_for_deletion_from_case(case_object, subcase_count)
                        subcase_count -= 1
                    if const.CASE_ACTION_CLOSE in actions:
                        reopened_cases[touched_id] = form_id
                        case_names[touched_id] = case_object.name
                    if any(action in actions for action in update_actions):
                        if touched_id not in affected_cases:
                            affected_cases[touched_id] = {}
                        affected_cases[touched_id][form_id] = ', '.join(actions)
                        case_names[touched_id] = case_object.name
            cases[case.case_id][form_id] = case_actions
        return

    case_instance = safely_get_case(request, domain, case_id)
    subcase_count = 0
    try:
        get_forms_for_deletion_from_case(case_instance, subcase_count)
    except ValueError:
        messages.error(request, _("Deleting this case would delete too many related cases. "
                                  "Please delete some of this cases' subcases before attempting"
                                  "to delete this case."))
        return {}, True

    def get_case_link(caseid):
        url = reverse('case_data', args=[domain, caseid])
        return mark_safe('<a href="{}"> {} </a>'.format(url, case_names[caseid]))

    def get_form_link(formid):
        url = reverse('render_form_data', args=[domain, formid])
        return mark_safe('<a href="{}"> {} </a>'.format(url, form_names[formid]))

    prepared_cases = {}
    for case in cases:
        prepared_forms = {}
        for form in cases[case]:
            form_link = get_form_link(form)
            prepared_forms[form_link] = {}
            for case_action in cases[case][form]:
                prepared_forms[form_link][case_action] = ', '.join(cases[case][form][case_action])
        prepared_cases[get_case_link(case)] = prepared_forms

    prepared_reopened_cases = {}
    for case in reopened_cases:
        prepared_reopened_cases[get_case_link(case)] = get_form_link(reopened_cases[case])

    prepared_affected_cases = {}
    for case in affected_cases:
        if case in delete_cases:
            continue
        prepared_forms = {}
        for form in affected_cases[case]:
            prepared_forms[get_form_link(form)] = affected_cases[case][form]
        prepared_affected_cases[get_case_link(case)] = prepared_forms

    return {
        'main_case_name': case_instance.name,
        'delete_dict': prepared_cases,
        'affected_cases': prepared_affected_cases,
        'reopened_cases': prepared_reopened_cases,
        'case_delete_list': delete_cases,
        'form_delete_list': delete_forms,
    }, False


@location_safe
class DeleteCaseView(BaseProjectReportSectionView):
    urlname = 'soft_delete_case_view'
    page_title = gettext_lazy('Delete Case and Related Forms')
    template_name = 'reports/reportdata/case_delete.html'
    delete_dict = {}

    @method_decorator(require_case_view_permission)
    def dispatch(self, request, *args, **kwargs):
        self.delete_dict, redirect = get_cases_and_forms_for_deletion(request, self.domain, self.case_id)
        if redirect:
            return HttpResponseRedirect(reverse('case_data', args=[self.domain, self.case_id]))
        return super(DeleteCaseView, self).dispatch(request, *args, **kwargs)

    @property
    def case_id(self):
        return self.kwargs['case_id']

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.case_id))

    @property
    def page_context(self):
        context = {
            "case_id": self.case_id,
        }
        context.update(self.delete_dict)
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('input') != self.delete_dict['main_case_name']:
            messages.error(request, "Incorrect name. Please enter the case name as shown into the textbox.")
            return HttpResponseRedirect(self.page_url)
        msg, error = soft_delete_cases_and_forms(request, self.domain, self.delete_dict['case_delete_list'],
                                      self.delete_dict['form_delete_list'])
        if error:
            messages.error(request, msg, extra_tags='html')
            return HttpResponseRedirect(reverse('case_data', args=[self.domain, self.case_id]))
        else:
            msg = self.delete_dict['main_case_name'] + msg
            messages.success(request, msg)
            return HttpResponseRedirect(reverse('project_report_dispatcher',
                                                args=(self.domain, 'submit_history')))


@location_safe
@require_permission(HqPermissions.edit_data)
def soft_delete_cases_and_forms(request, domain, case_delete_list, form_delete_list):
    """
    Archiving the form that created the case will automatically "unmake" the case, but won't delete
    the case from the database. This deletion will happen 90 days from the deletion date by an
    automated deletion task.
    """
    error = False
    msg = ", its related subcases and submission forms were deleted successfully."
    for form in form_delete_list:
        if archive_form(request, domain, form, is_case_delete=True):
            form_instance = XFormInstance.objects.get_form(form, domain)
            form_instance.soft_delete()
        else:
            # I'm fairly certain this will never enter here but this is just in case something does go wrong
            error = True
            msg = "The form {} could not be deleted. Please try manually archiving, then deleting the form," \
                  "before trying to delete this case again.".format(form)
            break
    if not error:
        CommCareCase.objects.soft_delete_cases(domain, list(case_delete_list))

    return msg, error


@location_safe
@require_case_view_permission
@require_permission(HqPermissions.edit_data)
@require_POST
def undo_close_case_view(request, domain, case_id, xform_id):
    case = safely_get_case(request, domain, case_id)
    if not case.closed:
        messages.info(request, 'Case {} is not closed.'.format(case.name))
    else:
        closing_form_id = xform_id
        assert closing_form_id in case.xform_ids
        form = XFormInstance.objects.get_form(closing_form_id, domain)
        form.archive(user_id=request.couch_user._id)
        messages.success(request, 'Case {} has been reopened.'.format(case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def export_case_transactions(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    products_by_id = dict(SQLProduct.objects.filter(domain=domain).values_list('product_id', 'name'))

    headers = [
        _('case id'),
        _('case name'),
        _('section'),
        _('date'),
        _('product_id'),
        _('product_name'),
        _('transaction amount'),
        _('type'),
        _('ending balance'),
    ]

    def _make_row(transaction):
        return [
            transaction.case_id,
            case.name,
            transaction.section_id,
            transaction.report_date or '',
            transaction.entry_id,
            products_by_id.get(transaction.entry_id, _('unknown product')),
            transaction.delta,
            transaction.type,
            transaction.stock_on_hand,
        ]

    transactions = sorted(
        LedgerAccessors.get_ledger_transactions_for_case(case_id),
        key=lambda tx: (tx.section_id, tx.report_date)
    )

    formatted_table = [
        [
            'ledger transactions',
            [headers] + [_make_row(txn) for txn in transactions]
        ]
    ]
    tmp = io.StringIO()
    export_from_tables(formatted_table, tmp, 'xlsx')
    return export_response(tmp, 'xlsx', '{}-stock-transactions'.format(case.name))
