import json
from urllib.parse import SplitResult

import urllib3
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View

import pytz
from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.data_interfaces.tasks import task_operate_on_payloads, task_generate_ids_and_operate_on_payloads
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.form_processor.exceptions import XFormNotFound
from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    get_paged_repeat_records,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
    get_cancelled_repeat_record_count,
    get_pending_repeat_record_count
)
from corehq.motech.repeaters.forms import EmailBulkPayload
from corehq.motech.repeaters.models import RepeatRecord
from corehq.motech.utils import pformat_json
from corehq.util.xml_utils import indent_xml

import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error

from soil.util import expose_cached_download


class DomainForwardingRepeatRecords(GenericTabularReport):
    name = 'Repeat Records'
    base_template = 'repeaters/repeat_record_report.html'
    section_name = 'Project Settings'
    slug = 'repeat_record_report'
    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    asynchronous = False
    sortable = False
    custom_filter_action_template = "domain/partials/custom_repeat_record_report.html"

    fields = [
        'corehq.apps.reports.filters.select.RepeaterFilter',
        'corehq.apps.reports.filters.select.RepeatRecordStateFilter',
        'corehq.apps.reports.filters.simple.RepeaterPayloadIdFilter',
    ]

    def _make_cancel_payload_button(self, record_id):
        return '''
                <a
                    class="btn btn-default cancel-record-payload"
                    role="button"
                    data-record-id={}>
                    Cancel Payload
                </a>
                '''.format(record_id)

    def _make_requeue_payload_button(self, record_id):
        return '''
                <a
                    class="btn btn-default requeue-record-payload"
                    role="button"
                    data-record-id={}>
                    Requeue Payload
                </a>
                '''.format(record_id)

    def _make_view_payload_button(self, record_id):
        return '''
        <a
            class="btn btn-default"
            role="button"
            data-record-id={}
            data-toggle="modal"
            data-target="#view-record-payload-modal">
            View Payload
        </a>
        '''.format(record_id)

    def _make_resend_payload_button(self, record_id):
        return '''
        <button
            class="btn btn-default resend-record-payload"
            data-record-id={}>
            Resend Payload
        </button>
        '''.format(record_id)

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
        return '''
        <span class="label label-{}">
            {}
        </span>
        '''.format(*self._get_state(record))

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
    def rows(self):
        self.repeater_id = self.request.GET.get('repeater', None)
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
        return (
            '<a href="{url}?q={payload_id}">'
            '<img src="{flower}" title="Search in HQ" width="14px" height="14px" />'
            '</a> {payload_id}'
        ).format(
            url=reverse('global_quick_find'),
            flower=static('hqwebapp/images/commcare-flower.png'),
            payload_id=payload_id,
        )

    def _make_row(self, record):
        checkbox = mark_safe(
            """<input type="checkbox" onclick="uncheckAlls()" class="xform-checkbox"
            value="{}" name="xform_ids"/>""".format(record.get_id)
        )
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

    @property
    def headers(self):
        columns = [
            DataTablesColumn(
                mark_safe(
                    """
                    Select  <a onclick="selectItems()" class="select-visible btn btn-xs btn-default">all</a>
                    <a onclick="unSelectItems()" class="select-none btn btn-xs btn-default">none</a>
                    """
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
        context = super(DomainForwardingRepeatRecords, self).report_context

        total = get_repeat_record_count(self.domain)
        total_cancel = get_cancelled_repeat_record_count(self.domain, None)
        total_requeue = get_pending_repeat_record_count(self.domain, None)

        form_query_string = self.request.GET.urlencode()
        form_query_string_requeue = _change_record_state(form_query_string, 'CANCELLED')
        form_query_string_cancellable = _change_record_state(form_query_string, 'PENDING')

        context.update(
            email_bulk_payload_form=EmailBulkPayload(domain=self.domain),
            total=total,
            total_cancel=total_cancel,
            total_requeue=total_requeue,
            form_query_string=form_query_string,
            form_query_string_cancellable=form_query_string_cancellable,
            form_query_string_requeue=form_query_string_requeue,
        )
        return context


@method_decorator(domain_admin_required, name='dispatch')
class RepeatRecordView(View):
    urlname = 'repeat_record'
    http_method_names = ['get', 'post']

    @staticmethod
    def get_record_or_404(request, domain, record_id):
        try:
            record = RepeatRecord.get(record_id)
        except ResourceNotFound:
            raise Http404()

        if record.domain != domain:
            raise Http404()

        return record

    def get(self, request, domain):
        record_id = request.GET.get('record_id')
        record = self.get_record_or_404(request, domain, record_id)
        content_type = record.repeater.generator.content_type
        try:
            payload = record.get_payload()
        except XFormNotFound:
            return json_response({
                'error': 'Odd, could not find payload for: {}'.format(record.payload_id)
            }, status_code=404)

        if content_type == 'text/xml':
            payload = indent_xml(payload)
        elif content_type == 'application/json':
            payload = pformat_json(payload)

        return json_response({
            'payload': payload,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        flag = _get_flag(request)
        if flag:
            _schedule_task_with_flag(request, domain, 'resend')
        else:
            _schedule_task_without_flag(request, domain, 'resend')

        return HttpResponse('OK')


@require_POST
@require_can_edit_web_users
def cancel_repeat_record(request, domain):
    flag = _get_flag(request)
    if flag == 'cancel_all':
        _schedule_task_with_flag(request, domain, 'cancel')
    else:
        _schedule_task_without_flag(request, domain, 'cancel')

    return HttpResponse('OK')


@require_POST
@require_can_edit_web_users
def requeue_repeat_record(request, domain):
    flag = _get_flag(request)
    if flag == 'requeue_all':
        _schedule_task_with_flag(request, domain, 'requeue')
    else:
        _schedule_task_without_flag(request, domain, 'requeue')

    return HttpResponse('OK')


def _get_records(request):
    records = request.POST.get('record_id')
    if not records:
        return []

    records_ids = records.split(' ')
    if records_ids[-1] == '':
        records_ids.pop()

    return records_ids


def _get_query(request):
    query = request.POST.get('record_id')
    return query if query else ''


def _get_flag(request):
    flag = request.POST.get('flag')
    return flag


def _change_record_state(base_string, string_to_add):
    string_to_look_for = 'record_state='
    pos_start = 0
    pos_end = 0
    for r in range(len(base_string)):
        if base_string[r:r+13] == string_to_look_for:
            pos_start = r + 13
            break

    string_to_look_for = '&payload_id='
    the_rest_of_string = base_string[pos_start:]
    for r in range(len(the_rest_of_string)):
        if the_rest_of_string[r:r+12] == string_to_look_for:
            pos_end = r
            break

    string_to_return = base_string[:pos_start] + string_to_add + the_rest_of_string[pos_end:] \
        if base_string != '' else base_string

    return string_to_return


def _url_parameters_to_dict(url_params):
    dict_to_return = {}
    while url_params != '':
        pos_one = url_params.find('=')
        pos_two = url_params.find('&')
        if pos_two == -1:
            pos_two = len(url_params)
        key = url_params[:pos_one]
        value = url_params[pos_one+1:pos_two]
        dict_to_return[key] = value
        url_params = url_params[pos_two+1:] if pos_two != len(url_params) else ''

    return dict_to_return


def _schedule_task_with_flag(request, domain, action):
    query = _get_query(request)
    data = None
    if query:
        form_query_string = six.moves.urllib.parse.unquote(query)
        data = _url_parameters_to_dict(form_query_string)
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    task = task_generate_ids_and_operate_on_payloads.delay(data, domain, action)
    task_ref.set_task(task)


def _schedule_task_without_flag(request, domain, action):
    records = _get_records(request)
    task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
    task = task_operate_on_payloads.delay(records, domain, action)
    task_ref.set_task(task)
