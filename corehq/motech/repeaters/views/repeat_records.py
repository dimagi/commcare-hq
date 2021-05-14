from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    QueryDict,
)
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View

import pytz
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

from ..const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from ..dbaccessors import (
    get_cancelled_repeat_record_count,
    get_paged_repeat_records,
    get_pending_repeat_record_count,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
)
from ..models import RepeatRecord, are_repeat_records_migrated, is_queued


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
            View Payload
        </a>
        ''', record_id)

    def _make_resend_payload_button(self, record_id):
        return format_html('''
        <button
            class="btn btn-default resend-record-payload"
            data-record-id={}>
            Resend Payload
        </button>
        ''', record_id)

    def _get_state(self, record):
        if record.state == RECORD_SUCCESS_STATE:
            label_cls = 'success'
            label_text = _('Success')
        elif record.state == RECORD_PENDING_STATE:
            label_cls = 'warning'
            label_text = _('Pending')
        elif record.state == RECORD_CANCELLED_STATE:
            label_cls = 'danger'
            label_text = _('Cancelled')
        elif record.state == RECORD_FAILURE_STATE:
            label_cls = 'danger'
            label_text = _('Failed')
        else:
            label_cls = ''
            label_text = ''

        return (label_cls, label_text)

    def _make_state_label(self, record):
        return format_html('<span class="label label-{}">{}</span>', *self._get_state(record))

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

    def _format_date(self, date):
        tz_utc_aware_date = pytz.utc.localize(date)
        return tz_utc_aware_date.astimezone(self.timezone).strftime('%b %d, %Y %H:%M:%S %Z')

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
        self.state = self.request.GET.get('record_state', None)
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
        raise NotImplementedError

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
            DataTablesColumn(_('URL')),
            DataTablesColumn(_('Last sent date')),
            DataTablesColumn(_('Retry Date')),
            DataTablesColumn(_('Delivery Attempts')),
            DataTablesColumn(_('View payload')),
            DataTablesColumn(_('Resend')),
            DataTablesColumn(_('Cancel or Requeue payload'))
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


class DomainForwardingRepeatRecords(BaseRepeatRecordReport):
    slug = 'couch_repeat_record_report'

    def _make_row(self, record):
        checkbox = format_html(
            '<input type="checkbox" class="xform-checkbox" data-id="{}" name="xform_ids"/>',
            record.get_id)
        row = [
            checkbox,
            self._make_state_label(record),
            record.repeater.get_url(record) if record.repeater else _('Unable to generate url for record'),
            self._format_date(record.last_checked) if record.last_checked else '---',
            self._format_date(record.next_check) if record.next_check else '---',
            render_to_string('repeaters/partials/attempt_history.html', {'record': record}),
            self._make_view_payload_button(record.get_id),
            self._make_resend_payload_button(record.get_id),
        ]

        if record.cancelled and not record.succeeded:
            row.append(self._make_requeue_payload_button(record.get_id))
        elif not record.cancelled and not record.succeeded:
            row.append(self._make_cancel_payload_button(record.get_id))
        else:
            row.append(None)

        if toggles.SUPPORT.enabled_for_request(self.request):
            row.insert(2, self._payload_id_and_search_link(record.payload_id))
        return row


class SQLRepeatRecordReport(BaseRepeatRecordReport):
    slug = 'repeat_record_report'

    def _make_row(self, record):
        checkbox = format_html(
            '<input type="checkbox" class="xform-checkbox" data-id="{}" name="xform_ids"/>',
            record.pk)
        if record.attempts:
            # Use prefetched `record.attempts` instead of requesting a
            # different queryset
            created_at = self._format_date(list(record.attempts)[-1].created_at)
        else:
            created_at = '---'
        if record.repeater_stub.next_attempt_at:
            next_attempt_at = self._format_date(record.repeater_stub.next_attempt_at)
        else:
            next_attempt_at = '---'
        row = [
            checkbox,
            self._make_state_label(record),
            record.repeater_stub.repeater.get_url(record),
            created_at,
            next_attempt_at,
            render_to_string('repeaters/partials/attempt_history.html',
                             {'record': record}),
            self._make_view_payload_button(record.pk),
            self._make_resend_payload_button(record.pk),
        ]

        if record.state == RECORD_CANCELLED_STATE:
            row.append(self._make_requeue_payload_button(record.pk))
        elif is_queued(record):
            row.append(self._make_cancel_payload_button(record.pk))
        else:
            row.append(None)

        if toggles.SUPPORT.enabled_for_request(self.request):
            row.insert(2, self._payload_id_and_search_link(record.payload_id))
        return row


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
        content_type = record.repeater.generator.content_type
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

        return JsonResponse({
            'payload': payload,
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
