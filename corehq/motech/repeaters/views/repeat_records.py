import json
import re
from typing import Literal

from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View

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
from corehq.motech.dhis2.parse_response import (
    get_diagnosis_message,
    get_errors,
)
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater
from corehq.motech.models import RequestLog
from corehq.motech.utils import pformat_json
from corehq.util.xml_utils import indent_xml

from ..const import State
from ..exceptions import BulkActionMissingParameters
from ..models import RepeatRecord
from .repeat_record_display import RepeatRecordDisplay


class DomainForwardingRepeatRecords(GenericTabularReport):
    name = 'Repeat Records'
    slug = 'repeat_record_report'
    base_template = 'repeaters/bootstrap3/repeat_record_report.html'
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_repeaters_enabled = toggles.PROCESS_REPEATERS.enabled(
            self.domain,
            toggles.NAMESPACE_DOMAIN,
        )

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

    @property
    def total_records(self):
        if self.payload_id:
            return len(self._get_all_records_by_payload())
        query = RepeatRecord.objects.filter(domain=self.domain)
        if self.repeater_id:
            query = query.filter(repeater_id=self.repeater_id)
        if self.state:
            query = query.filter(state=self.state)
        return query.count()

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': 'repeater', 'value': self.request.GET.get('repeater')},
            {'name': 'record_state', 'value': self.request.GET.get('record_state')},
            {'name': 'payload_id', 'value': self.request.GET.get('payload_id')},
        ]

    @memoized
    def _get_all_records_by_payload(self):
        query = RepeatRecord.objects.filter(
            domain=self.domain,
            payload_id=self.payload_id,
        )
        if self.repeater_id:
            query = query.filter(repeater_id=self.repeater_id)
        if self.state:
            query = query.filter(state=self.state)
        return list(query)

    @property
    def payload_id(self):
        return self.request.GET.get('payload_id', None)

    @property
    def repeater_id(self):
        return self.request.GET.get('repeater', None)

    @property
    def state(self):
        return State.state_for_key(self.request.GET.get('record_state'))

    @property
    def rows(self):
        if self.payload_id:
            end = self.pagination.start + self.pagination.count
            records = self._get_all_records_by_payload()[self.pagination.start:end]
        else:
            records = RepeatRecord.objects.page(
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
        display = RepeatRecordDisplay(
            record,
            self.timezone,
            date_format='%b %d, %Y %H:%M:%S %Z',
            process_repeaters_enabled=self.process_repeaters_enabled,
        )
        checkbox = format_html(
            '<input type="checkbox" class="record-checkbox" data-id="{}" name="record_ids" is_queued="{}"/>',
            record.id,
            1 if record.is_queued else 0,
        )
        row = [
            checkbox,
            display.state,
            display.remote_service,
            display.next_check,
            self._make_view_attempts_button(record.id),
            self._make_view_payload_button(record.id),
        ]

        if toggles.SUPPORT.enabled_for_request(self.request):
            row.insert(2, self._payload_id_and_search_link(record.payload_id))
        return row

    @property
    def headers(self):
        columns = [
            DataTablesColumn(
                format_html('<input type="checkbox" id="select-all-checkbox"></input>'),
                sortable=False, span=3
            ),
            DataTablesColumn(_('Status')),
            DataTablesColumn(_('Remote Service')),
            DataTablesColumn(_('Retry Date')),
            DataTablesColumn(_('Delivery Attempts')),
            DataTablesColumn(_('View Responses')),
        ]
        if toggles.SUPPORT.enabled_for_request(self.request):
            columns.insert(2, DataTablesColumn(_('Payload ID')))

        return DataTablesHeader(*columns)

    @property
    def report_context(self):
        context = super().report_context

        where = Q(domain=self.domain)
        if self.repeater_id:
            where &= Q(repeater_id=self.repeater_id)
        if self.payload_id:
            where &= Q(payload_id=self.payload_id)
        if self.state:
            where &= Q(state=self.state)
        total = RepeatRecord.objects.filter(where).count()

        context.update(
            total=total,
            payload_id=self.payload_id,
            repeater_id=self.repeater_id,
            state=self.state.name.upper() if self.state else None,
        )
        return context


@method_decorator(domain_admin_required, name='dispatch')
@method_decorator(requires_privilege_with_fallback(privileges.DATA_FORWARDING), name='dispatch')
class RepeatRecordView(View):
    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    @staticmethod
    def get_record_or_404(domain, record_id):
        try:
            record = RepeatRecord.objects.get(id=record_id)
        except RepeatRecord.DoesNotExist:
            raise Http404()

        if record.domain != domain:
            raise Http404()

        return record

    def get(self, request, domain):
        record_id = request.GET.get('record_id')
        record = self.get_record_or_404(domain, record_id)
        content_type = record.repeater.generator.content_type
        try:
            payload = record.get_payload()
        except XFormNotFound:
            return JsonResponse({
                'error': 'Odd, could not find payload for: {}'.format(record.payload_id)
            }, status=404)

        if content_type == 'text/xml':
            payload = indent_xml(payload)
        elif content_type in ['application/json', 'application/x-www-form-urlencoded']:
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
            'repeaters/partials/bootstrap3/attempt_history.html',
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
        if request.POST.get('record_id'):
            _schedule_task_without_state(request, domain, 'resend')
        else:
            try:
                _schedule_task_with_state(request, domain, 'resend')
            except BulkActionMissingParameters:
                return _missing_parameters_response()
        return JsonResponse({'success': True})


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def cancel_repeat_record(request, domain):
    if request.POST.get('record_id'):
        _schedule_task_without_state(request, domain, 'cancel')
    else:
        try:
            _schedule_task_with_state(request, domain, 'cancel')
        except BulkActionMissingParameters:
            return _missing_parameters_response()

    return HttpResponse('OK')


@require_POST
@require_can_edit_web_users
@requires_privilege_with_fallback(privileges.DATA_FORWARDING)
def requeue_repeat_record(request, domain):
    if request.POST.get('record_id'):
        _schedule_task_without_state(request, domain, 'requeue')
    else:
        try:
            _schedule_task_with_state(request, domain, 'requeue')
        except BulkActionMissingParameters:
            return _missing_parameters_response()

    return HttpResponse('OK')


def _missing_parameters_response():
    return JsonResponse(
        {
            "failure_reason": _(
                "Please filter to a specific repeater or payload before attempting a bulk action."
            )
        }
    )


def _get_record_ids_from_request(request):
    record_ids = request.POST.get('record_id') or ''
    return record_ids.strip().split()


def _get_state(request: HttpRequest) -> str:
    state_from_request = request.POST.get('state')
    if not state_from_request:
        return None
    state = State.state_for_key(state_from_request)
    if not state:
        raise KeyError(f"{state_from_request} is not a valid option for RepeatRecord.State")
    return state


def _schedule_task_with_state(
    request: HttpRequest,
    domain: str,
    action: Literal['resend', 'cancel', 'requeue']
):
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    payload_id = request.POST.get('payload_id', None)
    repeater_id = request.POST.get('repeater_id', None)
    if not any([repeater_id, payload_id]):
        raise BulkActionMissingParameters
    state = _get_state(request)
    task = task_generate_ids_and_operate_on_payloads.delay(
        payload_id, repeater_id, domain, action, state=state)
    task_ref.set_task(task)


def _schedule_task_without_state(
    request: HttpRequest,
    domain: str,
    action: Literal['resend', 'cancel', 'requeue']
):
    record_ids = _get_record_ids_from_request(request)
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    task = task_operate_on_payloads.delay(record_ids, domain, action)
    task_ref.set_task(task)
