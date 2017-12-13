from __future__ import absolute_import
from datetime import datetime, timedelta

from django.conf import settings
from dimagi.utils.chunked import chunked
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.urls import reverse
from dimagi.utils.decorators.memoized import memoized

from corehq.elastic import ES_MAX_CLAUSE_COUNT
from corehq.apps.es.case_search import flatten_result
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import MessagingEvent
from casexml.apps.case.models import CommCareCase
from corehq.motech.repeaters.dbaccessors import (
    iter_repeat_records_by_domain,
    get_repeat_record_count,
    get_repeat_records_by_payload_id
)
from corehq.apps.domain.views import DomainForwardingRepeatRecords
from corehq.apps.es import CaseSearchES
from corehq.apps.reports.generic import GenericTabularReport
from corehq.motech.repeaters.dbaccessors import get_repeaters_by_domain
from corehq.apps.reports.filters.select import RepeaterFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn

from custom.enikshay.case_utils import get_person_case, CASE_TYPE_VOUCHER
from custom.enikshay.exceptions import ENikshayException
from custom.enikshay.reports.filters import VoucherStateFilter, DistrictLocationFilter, VoucherIDFilter
from custom.enikshay.integrations.bets.repeaters import ChemistBETSVoucherRepeater, LabBETSVoucherRepeater
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from corehq.apps.reports.filters.select import RepeatRecordStateFilter
from dimagi.utils.modules import to_function


class ENikshayRepeaterFilter(RepeaterFilter):

    def __init__(self, *args, **kwargs):
        super(ENikshayRepeaterFilter, self).__init__(*args, **kwargs)
        self.enikshay_repeaters = tuple(to_function(cls, failhard=True) for cls in settings.ENIKSHAY_REPEATERS)

    def _get_repeaters(self):
        return [
            repeater for repeater in get_repeaters_by_domain(self.domain)
            if isinstance(repeater, self.enikshay_repeaters)
        ]


class ENikshayForwarderReport(DomainForwardingRepeatRecords):
    name = 'eNikshay Forwarder Report'
    base_template = 'reports/base_template.html'
    asynchronous = True
    section_name = 'Custom Reports'
    slug = 'enikshay_repeater_report'
    dispatcher = CustomProjectReportDispatcher
    fields = (ENikshayRepeaterFilter, RepeatRecordStateFilter)
    exportable = True
    exportable_all = True

    emailable = True

    @property
    def get_all_rows(self):
        repeater_id = self.request.GET.get('repeater', None)
        state = self.request.GET.get('record_state', None)
        if self.is_rendered_as_email:
            same_time_yesterday = datetime.today() - timedelta(days=1)
            return [
                [
                    get_repeat_record_count(self.domain, repeater_id, "SUCCESS"),
                    get_repeat_record_count(self.domain, repeater_id, "SUCCESS", same_time_yesterday),
                    get_repeat_record_count(self.domain, repeater_id, "CANCELLED"),
                    get_repeat_record_count(self.domain, repeater_id, "CANCELLED", same_time_yesterday),
                ]
            ]
        return [self._make_row(record) for record in
                iter_repeat_records_by_domain(self.domain, repeater_id=repeater_id, state=state)]

    @property
    def headers(self):
        if self.is_rendered_as_email:
            columns = [
                DataTablesColumn(_('Successful Records')),
                DataTablesColumn(_('Successful Records in Last 24 hours')),
                DataTablesColumn(_('Cancelled Records')),
                DataTablesColumn(_('Cancelled Records in Last 24 hours')),
            ]
        else:
            columns = [
                DataTablesColumn(_('Record ID')),
                DataTablesColumn(_('Status')),
                DataTablesColumn(_('Person Case')),
                DataTablesColumn(_('Payload Case')),
                DataTablesColumn(_('URL')),
                DataTablesColumn(_('Last sent date')),
                DataTablesColumn(_('Attempts')),
            ]
        return DataTablesHeader(*columns)

    def _make_row(self, record):
        attempt_messages = [
            escape("{date}: {message}".format(
                date=self._format_date(attempt.datetime),
                message=attempt.message))
            for attempt in record.attempts]

        row = [
            record._id,
            self._get_state(record)[1],
            self._get_person_id_link(record),
            self._get_case_id_link(record.payload_id),
            record.url if record.url else _(u'Unable to generate url for record'),
            self._format_date(record.last_checked) if record.last_checked else '---',
            ",<br />".join(attempt_messages),
        ]
        return row

    def _get_person_id_link(self, record):
        try:
            person_id = get_person_case(self.domain, record.payload_id).case_id
            return self._get_case_id_link(person_id)
        except ENikshayException as error:
            return u"Error: {}".format(error)

    def _get_case_id_link(self, case_id):
        return '<a href="{url}" target="_blank">{case_id}</a>'.format(
            url=reverse('case_details', args=[self.domain, case_id]),
            case_id=case_id
        )


class ENikshayVoucherReport(GenericTabularReport):
    slug = 'enikshay_voucher_repeater_report'
    section_name = 'Custom Reports'
    name = 'BETS Voucher Report'

    base_template = 'reports/base_template.html'
    dispatcher = CustomProjectReportDispatcher
    exportable = True
    exportable_all = True

    asynchronous = True
    ajax_pagination = True

    sortable = False

    fields = (VoucherStateFilter, DistrictLocationFilter, VoucherIDFilter)

    @property
    def district_ids(self):
        return self.request.GET.getlist('district_ids')

    @property
    def voucher_state(self):
        return self.request.GET.get('voucher_state')

    @property
    def voucher_id(self):
        return self.request.GET.get('voucher_id')

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Voucher Case ID'),
            DataTablesColumn('Voucher Readable ID'),
            DataTablesColumn('Voucher Status'),
            DataTablesColumn('Voucher District ID'),
            DataTablesColumn('Voucher Type'),
            DataTablesColumn('Voucher Approved Amount'),
            DataTablesColumn('Voucher Beneficiary ID'),
            DataTablesColumn('Voucher Beneficiary Name'),
            DataTablesColumn('Voucher Issued by Name'),

            DataTablesColumn('Amount Paid'),
            DataTablesColumn('Date Paid'),
            DataTablesColumn('Comments'),
            DataTablesColumn('Payment Mode'),
            DataTablesColumn('Check Number'),
            DataTablesColumn('Bank Name'),
            DataTablesColumn('Reason Rejected'),
            DataTablesColumn('Date Rejected'),
            DataTablesColumn('Messaging Activity'),

            DataTablesColumn('BETS Sent Date'),
            DataTablesColumn('Forwading Status'),
            DataTablesColumn('BETS Response Message'),
        )

    @property
    def rows(self):
        return self.get_rows(paged=True)

    @property
    def get_all_rows(self):
        return self.get_rows(paged=False)

    def get_rows(self, paged=True):
        location_ids = self._get_voucher_location_ids()
        if location_ids:
            vouchers = []
            for location_id_chunk in chunked(location_ids, ES_MAX_CLAUSE_COUNT):
                vouchers += [
                    CommCareCase.wrap(flatten_result(result))
                    for result in self._search_results(paged, location_id_chunk).raw_hits
                ]
        else:
            vouchers = [
                CommCareCase.wrap(flatten_result(result))
                for result in self._search_results(paged).raw_hits
            ]

        return [row for voucher in vouchers for row in self._make_rows(voucher)]

    @memoized
    def _search_results(self, paged=True, location_ids=None):
        cs = (
            CaseSearchES()
            .domain(self.domain)
            .case_type(CASE_TYPE_VOUCHER)
        )

        if location_ids:
            cs = cs.case_property_query('voucher_fulfilled_by_location_id', " ".join(location_ids))

        if self.voucher_state:
            cs = cs.case_property_query('state', self.voucher_state)

        if self.voucher_id:
            cs = cs.case_property_query('voucher_id', self.voucher_id)

        if paged:
            cs = cs.start(self.pagination.start).size(self.pagination.count)

        return cs.run()

    @memoized
    def _get_voucher_location_ids(self):
        """Return all locations beneath the district that could own the voucher
        """
        district_locs = SQLLocation.active_objects.filter(location_id__in=self.district_ids)
        voucher_location_types = ['plc', 'pcc', 'pdr', 'dto']
        possible_location_ids = (
            SQLLocation.active_objects
            .get_queryset_descendants(district_locs, include_self=True)
            .filter(location_type__code__in=voucher_location_types)
            .values_list('location_id', flat=True)
        )
        return possible_location_ids

    def get_messaging_event_detail_link(self, messaging_event_id):
        return (
            '<a target="_blank" href="/a/%s/reports/message_event_detail/?id=%s">[%s]</a>' %
            (self.domain, messaging_event_id, messaging_event_id)
        )

    def get_messaging_event_links(self, voucher_case_id):
        event_pks = (
            MessagingEvent
            .objects
            .filter(domain=self.domain, messagingsubevent__case_id=voucher_case_id)
            .values_list('pk', flat=True)
            .distinct()
            .order_by('date')
        )

        return ', '.join([self.get_messaging_event_detail_link(pk) for pk in event_pks])

    def _make_rows(self, voucher):
        default_row = [
            voucher.case_id,
            voucher.get_case_property('voucher_id'),
            voucher.get_case_property('state'),
            voucher.get_case_property('voucher_district_id'),
            voucher.get_case_property('voucher_type'),
            voucher.get_case_property('amount_approved'),
            voucher.get_case_property('voucher_fulfilled_by_id'),
            voucher.get_case_property('voucher_fulfilled_by_name'),
            voucher.get_case_property('voucher_issued_by_name'),
            voucher.get_case_property('amount_paid'),
            voucher.get_case_property('date_paid'),
            voucher.get_case_property('comments'),
            voucher.get_case_property('payment_mode'),
            voucher.get_case_property('check_number'),
            voucher.get_case_property('bank_name'),
            voucher.get_case_property('reason_rejected'),
            voucher.get_case_property('date_rejected'),
            self.get_messaging_event_links(voucher.case_id),
        ]

        repeat_records = self._get_voucher_repeat_records(voucher.case_id)
        if not repeat_records:
            return [default_row + ["-", "-", "-"]]

        rows = []
        for repeat_record in repeat_records:
            attempt_messages = [
                escape("{date}: {message}".format(
                    date=attempt.datetime,
                    message=attempt.message))
                for attempt in repeat_record.attempts
            ]
            rows.append(
                default_row + [
                    repeat_record.last_checked if repeat_record.last_checked else '-',
                    repeat_record.state,
                    ",<br />".join(attempt_messages),
                ]
            )
        return rows

    def _get_voucher_repeat_records(self, voucher_id):
        repeat_records = get_repeat_records_by_payload_id(self.domain, voucher_id)
        return [r for r in repeat_records if r.repeater_id in self._get_voucher_repeater_ids()]

    def _get_voucher_repeater_ids(self):
        return [
            repeater._id for repeater in get_repeaters_by_domain(self.domain)
            if isinstance(repeater, (LabBETSVoucherRepeater, ChemistBETSVoucherRepeater))
        ]

    @property
    def total_records(self):
        location_ids = self._get_voucher_location_ids()
        if location_ids:
            total = 0
            for location_id_chunk in chunked(location_ids, ES_MAX_CLAUSE_COUNT):
                total += self._search_results(location_ids=location_id_chunk).total
        else:
            total = self._search_results().total
        return total

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='district_ids', value=self.district_ids),
            dict(name='voucher_state', value=self.voucher_state),
            dict(name='voucher_id', value=self.voucher_id),
        ]
