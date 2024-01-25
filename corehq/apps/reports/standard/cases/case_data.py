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
from django.utils.html import escape, format_html
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
from corehq.apps.app_manager.dbaccessors import get_latest_app_ids_and_versions
from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.data_dictionary.util import is_case_type_deprecated
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.export.const import KNOWN_CASE_PROPERTIES
from corehq.apps.export.models import CaseExportDataSchema
from corehq.apps.export.utils import is_occurrence_deleted
from corehq.apps.hqcase.utils import (
    CASEBLOCK_CHUNKSIZE,
    EDIT_FORM_XMLNS,
    resave_case,
    submit_case_blocks,
)
from corehq.apps.hqcase.case_deletion_utils import (
    AffectedForm,
    DeleteCase,
    DeleteForm,
    FormAffectedCases,
    get_all_cases_from_form,
    get_affected_case,
    get_ordered_case_xforms,
    ReopenedCase,
    validate_case_for_deletion,
)
from corehq.apps.hqwebapp.decorators import use_datatables
from corehq.apps.hqwebapp.doc_info import get_form_url, get_case_url
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
from corehq.apps.reports.display import xmlns_to_name, xmlns_to_name_case_deletion
from corehq.apps.reports.exceptions import TooManyCases
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


def safely_get_case(request, domain, case_id, include_deleted=False):
    """Get case if accessible else raise a 404 or 403"""
    case = get_case_or_404(domain, case_id, include_deleted)
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
        change_json['form_url'] = get_form_url(domain, change.transaction.form.form_id)
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
    return HttpResponseRedirect(get_case_url(domain, case_id))


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
    return HttpResponseRedirect(get_case_url(domain, case_id))


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
    return HttpResponseRedirect(get_case_url(domain, case_id))


MAX_CASE_COUNT = CASEBLOCK_CHUNKSIZE
MAX_SUBCASE_DEPTH = 3


def get_case_and_display_data(main_case_obj, domain, main_form_id=None):
    """
    Given a case object, recursively checks the case's related submission forms and for each form, the related
    cases it has affected, and so on, until it goes through all related cases and their related forms.
    This recursion is capped at the MAX_CASE_COUNT and MAX_SUBCASE_DEPTH values defined above.

    :param main_case_obj: The main case object targeted for deletion. If the case deletion began from form
    deletion, this is the first case returned while iterating through the form's case (create) updates.
    :param main_form_id: The form_id of the form being targeted for deletion. This is only applicable if
    a user is deleting a form that had previously created a case.
    :return: Returns a dictionary containing the two complete list of cases and forms to reference for
    soft deletion and 5 lists of dataclasses to be parsed by the html to show deleted, affected and reopened
    cases and their related submission forms.
    """
    delete_cases = []  # list of cases to be soft deleted
    delete_forms = []  # list of forms to be soft deleted

    # For formatting the list of cases/submission forms
    form_names = {}

    delete_cases_display = []
    form_delete_cases_display = []
    affected_cases_display = []
    form_affected_cases_display = []
    reopened_cases_display = []

    update_actions = [const.CASE_ACTION_INDEX,
                      const.CASE_ACTION_UPDATE,
                      const.CASE_ACTION_ATTACHMENT,
                      const.CASE_ACTION_COMMTRACK,
                      const.CASE_ACTION_REBUILD]

    def walk_case_relations(case, subcase_count):
        case = validate_case_for_deletion(case)
        if not case:
            return
        if case.case_id not in delete_cases:
            delete_cases.append(case.case_id)
            if len(delete_cases) > MAX_CASE_COUNT or subcase_count >= MAX_SUBCASE_DEPTH:
                raise TooManyCases("Too many cases to delete")
            current_case = DeleteCase(name=case.name, url=get_case_url(domain, case.case_id))
            if len(delete_cases) == 1:
                current_case.is_primary = True
            delete_cases_display.append(current_case)
        xform_objs = get_ordered_case_xforms(case, domain)

        # iterating through all forms that updated the case (includes archived forms)
        for form_obj in xform_objs:
            form_id = form_obj.form_id
            if form_id not in delete_forms:
                delete_forms.insert(0, form_id)
            if form_id not in form_names:
                form_names[form_id] = escape(xmlns_to_name_case_deletion(domain, form_obj))
            current_form = DeleteForm(name=form_names[form_id], url=get_form_url(domain, form_id))
            if main_form_id and form_id == main_form_id:
                current_form.is_primary = True
                form_delete_cases_display.append(current_case)
                delete_cases_display.remove(current_case)
            current_case.delete_forms.append(current_form)

            touched_cases = get_all_cases_from_form(form_obj, domain)
            case_actions = []

            # iterating through all cases affected by the current form_obj
            for touched_id in touched_cases:
                case_obj = touched_cases[touched_id].case
                actions = list(touched_cases[touched_id].actions)
                if touched_id == case.case_id:
                    case_actions.append(FormAffectedCases(is_current_case=True, actions=', '.join(actions)))
                elif touched_id not in delete_cases:
                    case_actions.append(FormAffectedCases(case_name=case_obj.name,
                                                          actions=', '.join(actions)))
                    if const.CASE_ACTION_CREATE in actions and touched_id != case.case_id:
                        walk_case_relations(case_obj, subcase_count + 1)
                    if const.CASE_ACTION_CLOSE in actions:
                        reopened_cases_display.append(
                            ReopenedCase(name=case_obj.name, url=get_case_url(domain, touched_id),
                                         closing_form_url=get_form_url(domain, form_id),
                                         closing_form_name=form_names[form_id],
                                         closing_form_is_primary=current_form.is_primary))
                    if any(action in actions for action in update_actions):
                        affected_case = get_affected_case(domain, case_obj, affected_cases_display)
                        affected_form = AffectedForm(name=form_names[form_id],
                                                     url=get_form_url(domain, form_id),
                                                     actions=', '.join(actions),
                                                     is_primary=current_form.is_primary)
                        if affected_form.is_primary:
                            form_affected_cases_display.append(affected_case)
                            affected_cases_display.remove(affected_case)
                        affected_case.affected_forms.append(affected_form)
            current_form.affected_cases = case_actions

    walk_case_relations(main_case_obj, subcase_count=0)
    affected_cases_display = [case for case in affected_cases_display if case.id not in delete_cases]
    form_affected_cases_display = [case for case in form_affected_cases_display if case.id not in delete_cases]

    case_has_multiple_forms = False
    for case in form_delete_cases_display:
        if len(case.delete_forms) > 1:
            case_has_multiple_forms = True

    return {
        'case_delete_list': delete_cases,
        'form_delete_list': delete_forms,
        'delete_cases': delete_cases_display,
        'form_delete_cases': form_delete_cases_display,
        'affected_cases': affected_cases_display,
        'form_affected_cases': form_affected_cases_display,
        'reopened_cases': reopened_cases_display,
        'has_multiple_forms': case_has_multiple_forms,
    }


@location_safe
def get_cases_and_forms_for_deletion(request, domain, case_id, form_id=None):
    case_instance = safely_get_case(request, domain, case_id, include_deleted=True)
    try:
        case_data = get_case_and_display_data(case_instance, domain, form_id)
    except TooManyCases:
        if form_id:
            messages.error(request, _("Deleting this form would delete too many related cases. "
                                      "Please navigate to the form's Case Changes and delete some "
                                      "of the cases it created before attempting to delete this form."))
        else:
            messages.error(request, _("Deleting this case would delete too many related cases. "
                                      "Please delete some of this cases' subcases before attempting"
                                      "to delete this case."))
        return {'redirect': True}

    case_data.update({
        'main_case_name': case_instance.name,
        'redirect': False
    })
    return case_data


@location_safe
class DeleteCaseView(BaseProjectReportSectionView):
    urlname = 'soft_delete_case_view'
    page_title = gettext_lazy('Delete Case and Related Forms')
    template_name = 'reports/reportdata/case_delete.html'
    delete_dict = {}

    @method_decorator(require_case_view_permission)
    def dispatch(self, request, *args, **kwargs):
        if self.xform_id:
            self.template_name = 'reports/reportdata/form_case_delete.html'
            self.page_title = gettext_lazy('Delete Form and Related Cases')
        self.delete_dict = get_cases_and_forms_for_deletion(request, self.domain, self.case_id, self.xform_id)
        if self.delete_dict['redirect']:
            return HttpResponseRedirect(self.get_redirect_url())
        return super(DeleteCaseView, self).dispatch(request, *args, **kwargs)

    @property
    def case_id(self):
        return self.kwargs['case_id']

    @property
    def xform_id(self):
        if 'xform_id' in self.kwargs:
            return self.kwargs['xform_id']
        return None

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def page_url(self):
        if self.xform_id:
            return reverse(self.urlname, args=(self.domain, self.case_id, self.xform_id))
        return reverse(self.urlname, args=(self.domain, self.case_id))

    @property
    def page_context(self):
        context = {
            "main_case_id": self.case_id,
            "main_xform_id": self.xform_id,
        }
        context.update(self.delete_dict)
        return context

    def get_redirect_url(self):
        if self.xform_id:
            get_form_url(self.domain, self.xform_id)
        return get_case_url(self.domain, self.case_id)

    def post(self, request, *args, **kwargs):
        if request.POST.get('input') != self.delete_dict['main_case_name']:
            messages.error(request, "Incorrect name. Please enter the case name as shown into the textbox.")
            return HttpResponseRedirect(self.page_url)
        msg, error = soft_delete_cases_and_forms(request, self.domain, self.delete_dict['case_delete_list'],
                                      self.delete_dict['form_delete_list'])
        if error:
            messages.error(request, msg, extra_tags='html')
            return HttpResponseRedirect(self.get_redirect_url())
        else:
            msg = self.delete_dict['main_case_name'] + msg
            messages.success(request, msg)
            return HttpResponseRedirect(reverse('project_report_dispatcher',
                                                args=(self.domain, 'submit_history')))


@location_safe
@require_permission(HqPermissions.edit_data)
def soft_delete_cases_and_forms(request, domain, case_delete_list, form_delete_list):
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
    return HttpResponseRedirect(get_case_url(domain, case_id))


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
