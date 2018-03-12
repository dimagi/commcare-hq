from __future__ import absolute_import
import json
import pytz

from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic import View

from couchdbkit import ResourceNotFound
from memoized import memoized
from dimagi.utils.web import json_response

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.form_processor.exceptions import XFormNotFound
from corehq.motech.repeaters.forms import EmailBulkPayload
from corehq.util.xml_utils import indent_xml

from corehq.motech.repeaters.const import (
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_CANCELLED_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.dbaccessors import (
    get_paged_repeat_records,
    get_repeat_record_count,
    get_repeat_records_by_payload_id,
)
from corehq.motech.repeaters.models import RepeatRecord


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
            flower=static('prelogin/images/commcare-flower.png'),
            payload_id=payload_id,
        )

    def _make_row(self, record):
        row = [
            self._make_state_label(record),
            record.repeater.get_url(record) if record.repeater else _(u'Unable to generate url for record'),
            self._format_date(record.last_checked) if record.last_checked else '---',
            self._format_date(record.next_check) if record.next_check else '---',
            render_to_string('repeaters/partials/attempt_history.html', {'record': record}),
            self._make_view_payload_button(record.get_id),
            self._make_resend_payload_button(record.get_id),
            self._make_requeue_payload_button(record.get_id) if record.cancelled and not record.succeeded
            else self._make_cancel_payload_button(record.get_id) if not record.cancelled
            and not record.succeeded
            else None
        ]

        if toggles.SUPPORT.enabled_for_request(self.request):
            row.insert(1, self._payload_id_and_search_link(record.payload_id))
        return row

    @property
    def headers(self):
        columns = [
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
            columns.insert(1, DataTablesColumn(_('Payload ID')))

        return DataTablesHeader(*columns)

    @property
    def report_context(self):
        context = super(DomainForwardingRepeatRecords, self).report_context
        context.update(
            email_bulk_payload_form=EmailBulkPayload(domain=self.domain),
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
                'error': u'Odd, could not find payload for: {}'.format(record.payload_id)
            }, status_code=404)

        if content_type == 'text/xml':
            payload = indent_xml(payload)
        elif content_type == 'application/json':
            payload = json.dumps(json.loads(payload), indent=4)
        elif content_type == 'application/soap+xml':
            # we return a payload that is a dict, which is then converted to
            # XML by the zeep library before being sent along as a SOAP request.
            payload = json.dumps(payload, indent=4)

        return json_response({
            'payload': payload,
            'content_type': content_type,
        })

    def post(self, request, domain):
        # Retriggers a repeat record
        record_id = request.POST.get('record_id')
        record = self.get_record_or_404(request, domain, record_id)
        record.fire(force_send=True)
        return json_response({
            'success': record.succeeded,
            'failure_reason': record.failure_reason,
        })


@require_POST
@require_can_edit_web_users
def cancel_repeat_record(request, domain):
    try:
        record = RepeatRecord.get(request.POST.get('record_id'))
    except ResourceNotFound:
        return HttpResponse(status=404)
    record.cancel()
    record.save()
    if not record.cancelled:
        return HttpResponse(status=400)
    return HttpResponse('OK')


@require_POST
@require_can_edit_web_users
def requeue_repeat_record(request, domain):
    try:
        record = RepeatRecord.get(request.POST.get('record_id'))
    except ResourceNotFound:
        return HttpResponse(status=404)
    record.requeue()
    record.save()
    if record.cancelled:
        return HttpResponse(status=400)
    return HttpResponse('OK')
