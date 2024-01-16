import json
import re

from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    QueryDict,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View
from django.template.loader import render_to_string

from couchdbkit import ResourceNotFound
from memoized import memoized

from soil.util import expose_cached_download

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.data_interfaces.tasks import (
    task_generate_ids_and_operate_on_payloads,
    task_operate_on_payloads,
)
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.form_processor.exceptions import XFormNotFound
from corehq.motech.utils import pformat_json
from corehq.util.xml_utils import indent_xml
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater
from corehq.motech.dhis2.parse_response import get_errors, get_diagnosis_message
from corehq.motech.models import RequestLog

from ..const import State, RECORD_CANCELLED_STATE
from ..dbaccessors import (
    get_cancelled_repeat_record_count,
    get_paged_repeat_records,
    get_pending_repeat_record_count,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
)
from ..models import RepeatRecord, are_repeat_records_migrated, is_queued
from .repeat_record_display import RepeatRecordDisplay


class BaseRepeatRecordReport(GenericTabularReport):
    name = 'Repeat Records'
    base_template = 'repeaters/repeat_record_report.html'
    section_name = 'Project Settings'

    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    asynchronous = False
    sortable = False

    fields = [
        'corehq.apps.reports.filters.select.RepeaterFilter',
        'corehq.apps.reports.filters.select.RepeatRecordStateFilter',
        'corehq.apps.reports.filters.simple.RepeaterPayloadIdFilter',
    ]

    # Keys match RepeatRecordStateFilter.options[*][0]
    _state_map = {s.name.upper(): s for s in State}

    def _make_cancel_payload_button(self, record_id):
        return format_html('''
                <a
                    class="btn btn-default cancel-record-payload"
                    role="button"
                    data-record-id={}>
                    Cancel Payload
                </a>
                ''', record_id)

    def _make_requeue_payload_button(self, record_id):
        return format_html('''
                <a
                    class="btn btn-default requeue-record-payload"
                    role="button"
                    data-record-id={}>
                    Requeue Payload
                </a>
                ''', record_id)

    def _make_view_payload_button(self, record_id):
        return format_html('''
        <a
            class="btn btn-default"
            role="button"
            data-record-id={}
            data-toggle="modal"
            data-target="#view-record-payload-modal">
            <i class="fa fa-search"></i>
            Payload
        </a>
        ''', record_id)

    def _make_view_attempts_button(self, record_id):
        return format_html('''
        <button
            class="btn btn-default view-attempts-btn"
            data-record-id={}>
            <i class="fa fa-search"></i>
            Responses
        </button>
        ''', record_id)

    def _make_resend_payload_button(self, record_id):
        return format_html('''
        <button
            class="btn btn-default resend-record-payload"
            data-record-id={}>
            Resend Payload
        </button>
        ''', record_id)

    @property
    def total_records(self):
        if self.payload_id:
            return len(self._get_all_records_by_payload())
        else:
            return get_repeat_record_count(self.domain, self.repeater_id, self.state)

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': 'repeater', 'value': self.request.GET.get('repeater')},
            {'name': 'record_state', 'value': self.request.GET.get('record_state')},
            {'name': 'payload_id', 'value': self.request.GET.get('payload_id')},
        ]

    @memoized
    def _get_all_records_by_payload(self):
        # It is assumed that there are relatively few repeat records for a given payload,
        # so this is just filtered in memory.  If that changes, we should filter in the db.
        return [
            r for r in get_repeat_records_by_payload_id(self.domain, self.payload_id)
            if (not self.repeater_id or r.repeater_id == self.repeater_id)
            and (not self.state or r.state == self.state)
        ]

    @property
    def payload_id(self):
        return self.request.GET.get('payload_id', None)

    @property
    def repeater_id(self):
        return self.request.GET.get('repeater', None)

    @property
    def rows(self):
        self.state = self._state_map.get(self.request.GET.get('record_state'))
        if self.payload_id:
            end = self.pagination.start + self.pagination.count
            records = self._get_all_records_by_payload()[self.pagination.start:end]
        else:
            records = get_paged_repeat_records(
                self.domain,
                self.pagination.start,
                self.pagination.count,
                repeater_id=self.repeater_id,
                state=self.state
            )
        rows = [self._make_row(record) for record in records]
        return rows

    def _payload_id_and_search_link(self, payload_id):
        return format_html(
            '<a href="{url}?q={payload_id}">'
            '<img src="{flower}" title="Search in HQ" width="14px" height="14px" />'
            ' {payload_id}</a><br/>',
            '<a href="{log_url}?filter_payload={payload_id}" target="_blank">View Logs</a>',
            url=reverse('global_quick_find'),
            log_url=reverse('motech_log_list_view', args=[self.domain]),
            flower=static('hqwebapp/images/commcare-flower.png'),
            payload_id=payload_id,
        )

    def _make_row(self, record):
        display = RepeatRecordDisplay(record, self.timezone, date_format='%b %d, %Y %H:%M:%S %Z')
        checkbox = format_html(
            '<input type="checkbox" class="xform-checkbox" data-id="{}" name="xform_ids"/>',
            record.record_id)
        row = [
            checkbox,
            display.state,
            display.remote_service,
            display.next_attempt_at,
            self._make_view_attempts_button(record.record_id),
            self._make_view_payload_button(record.record_id),
            self._make_resend_payload_button(record.record_id),
        ]

        if self._is_cancelled(record):
            row.append(self._make_requeue_payload_button(record.record_id))
        elif self._is_queued(record):
            row.append(self._make_cancel_payload_button(record.record_id))
        else:
            row.append(None)

        if toggles.SUPPORT.enabled_for_request(self.request):
            row.insert(2, self._payload_id_and_search_link(record.payload_id))
        return row

    @property
    def headers(self):
        columns = [
            DataTablesColumn(
                format_html(
                    '{}<button id="all" class="select-visible btn btn-xs btn-default">{}</button>'
                    '<button id="none" class="select-none btn btn-xs btn-default">{}</button>',
                    _('Select'),
                    _('all'),
                    _('none')
                ),
                sortable=False, span=3
            ),
            DataTablesColumn(_('Status')),
            DataTablesColumn(_('Remote Service')),
            DataTablesColumn(_('Retry Date')),
            DataTablesColumn(_('Delivery Attempts')),
            DataTablesColumn(_('View Responses')),
            DataTablesColumn(_('Resend')),
            DataTablesColumn(_('Cancel or Requeue'))
        ]
        if toggles.SUPPORT.enabled_for_request(self.request):
            columns.insert(2, DataTablesColumn(_('Payload ID')))

        return DataTablesHeader(*columns)

    @property
    def report_context(self):
        context = super().report_context

        total = get_repeat_record_count(self.domain, self.repeater_id)
        total_pending = get_pending_repeat_record_count(self.domain, self.repeater_id)
        total_cancelled = get_cancelled_repeat_record_count(self.domain, self.repeater_id)

        form_query_string = self.request.GET.urlencode()
        form_query_string_cancelled = _change_record_state(
            self.request.GET, 'CANCELLED').urlencode()
        form_query_string_pending = _change_record_state(
            self.request.GET, 'PENDING').urlencode()

        context.update(
            total=total,
            total_pending=total_pending,
            total_cancelled=total_cancelled,
            form_query_string=form_query_string,
            form_query_string_pending=form_query_string_pending,
            form_query_string_cancelled=form_query_string_cancelled,
        )
        return context

    def _is_cancelled(self, record):
        raise NotImplementedError

    def _is_queued(self, record):
        raise NotImplementedError


class DomainForwardingRepeatRecords(BaseRepeatRecordReport):
    slug = 'couch_repeat_record_report'

    def _is_cancelled(self, record):
        return record.cancelled and not record.succeeded

    def _is_queued(self, record):
        return not record.cancelled and not record.succeeded


class SQLRepeatRecordReport(BaseRepeatRecordReport):
    slug = 'repeat_record_report'

    def _is_cancelled(self, record):
        return record.state == RECORD_CANCELLED_STATE

    def _is_queued(self, record):
        return is_queued(record)


@method_decorator(domain_admin_required, name='dispatch')
@method_decorator(requires_privilege_with_fallback(privileges.DATA_FORWARDING), name='dispatch')
class RepeatRecordView(View):
    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    @staticmethod
    def get_record_or_404(domain, record_id):
        try:
            record = RepeatRecord.get(record_id)
        except ResourceNotFound:
            raise Http404()

        if record.domain != domain:
            raise Http404()

        return record

    def get(self, request, domain):
        record_id = request.GET.get('record_id')
        record = self.get_record_or_404(domain, record_id)
        repeater = record.repeater
        if not repeater:
            return JsonResponse({
                'error': 'Repeater with id {} could not be found'.format(
                    record.repeater_id)
            }, status=404)
        content_type = repeater.generator.content_type
        try:
            payload = record.get_payload()
        except XFormNotFound:
            return JsonResponse({
                'error': 'Odd, could not find payload for: {}'.format(record.payload_id)
            }, status=404)

        if content_type == 'text/xml':
            payload = indent_xml(payload)
        elif content_type == 'application/json':
            payload = pformat_json(payload)

        dhis2_errors = []
        if toggles.DHIS2_INTEGRATION.enabled(domain) and isinstance(record.repeater, Dhis2EntityRepeater):
            logs = RequestLog.objects.filter(domain=domain, payload_id=record.payload_id)
            for log in logs:
                try:
                    resp_body = json.loads(log.response_body)
                    log_errors = [
                        (error, get_diagnosis_message(error)) for error in get_errors(resp_body).values()
                    ]
                    dhis2_errors += log_errors
                except json.JSONDecodeError:
                    # If it's not JSON, then we might be dealing with an HTML string, so remove HTML tags
                    tag_remove_regex = re.compile('<.*?>')
                    cleaned_log = re.sub(tag_remove_regex, '', log.response_body)
                    dhis2_errors.append((cleaned_log, get_diagnosis_message(cleaned_log)))

        attempt_html = render_to_string(
            'repeaters/partials/attempt_history.html',
            context={
                'record': record,
                'record_id': record_id,
                'dhis2_errors': dhis2_errors,
                'has_attempts': any(record.attempts),
                'has_dhis2_errors': any(dhis2_errors)
            }
        )

        return JsonResponse({
            'payload': payload,
            'attempts': attempt_html,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        use_sql = are_repeat_records_migrated(domain)
        if _get_flag(request):
            _schedule_task_with_flag(request, domain, 'resend', use_sql)
        else:
            _schedule_task_without_flag(request, domain, 'resend', use_sql)
        return JsonResponse({'success': True})


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def cancel_repeat_record(request, domain):
    use_sql = are_repeat_records_migrated(domain)
    if _get_flag(request) == 'cancel_all':
        _schedule_task_with_flag(request, domain, 'cancel', use_sql)
    else:
        _schedule_task_without_flag(request, domain, 'cancel', use_sql)

    return HttpResponse('OK')


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def requeue_repeat_record(request, domain):
    use_sql = are_repeat_records_migrated(domain)
    if _get_flag(request) == 'requeue_all':
        _schedule_task_with_flag(request, domain, 'requeue', use_sql)
    else:
        _schedule_task_without_flag(request, domain, 'requeue', use_sql)

    return HttpResponse('OK')


def _get_record_ids_from_request(request):
    record_ids = request.POST.get('record_id') or ''
    return record_ids.strip().split()


def _get_flag(request: HttpRequest) -> str:
    return request.POST.get('flag') or ''


def _change_record_state(query_dict: QueryDict, state: str) -> QueryDict:
    if not state:
        return query_dict
    if 'record_state' in query_dict:
        query_dict = query_dict.copy()  # Don't cause side effects. Also,
        # request.GET is immutable and will raise AttributeError.
        query_dict['record_state'] = state
    return query_dict


def _schedule_task_with_flag(
    request: HttpRequest,
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool,
):
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    payload_id = request.POST.get('payload_id') or None
    repeater_id = request.POST.get('repeater') or None
    task = task_generate_ids_and_operate_on_payloads.delay(
        payload_id, repeater_id, domain, action, use_sql)
    task_ref.set_task(task)


def _schedule_task_without_flag(
    request: HttpRequest,
    domain: str,
    action,  # type: Literal['resend', 'cancel', 'requeue']  # 3.8+
    use_sql: bool,
):
    record_ids = _get_record_ids_from_request(request)
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    task = task_operate_on_payloads.delay(record_ids, domain, action, use_sql)
    task_ref.set_task(task)
