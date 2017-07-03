from django.conf import settings
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.urls import reverse

from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain
from corehq.apps.domain.views import DomainForwardingRepeatRecords
from corehq.motech.repeaters.dbaccessors import get_repeaters_by_domain
from corehq.apps.reports.filters.select import RepeaterFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn

from custom.enikshay.case_utils import get_person_case
from custom.enikshay.exceptions import ENikshayException
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
    section_name = 'Custom Reports'
    slug = 'enikshay_repeater_report'
    dispatcher = CustomProjectReportDispatcher
    fields = (ENikshayRepeaterFilter, RepeatRecordStateFilter)
    exportable = True
    exportable_all = True

    @property
    def get_all_rows(self):
        repeater_id = self.request.GET.get('repeater', None)
        state = self.request.GET.get('record_state', None)
        return [self._make_row(record) for record in
                iter_repeat_records_by_domain(self.domain, repeater_id=repeater_id, state=state)]

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Record ID')),
            DataTablesColumn(_('Status')),
            DataTablesColumn(_('Person Case')),
            DataTablesColumn(_('URL')),
            DataTablesColumn(_('Last sent date')),
            DataTablesColumn(_('Failure Reason')),
            DataTablesColumn(_('Payload')),
        ]

        return DataTablesHeader(*columns)

    def _make_row(self, record):
        try:
            payload = record.get_payload()
        except ENikshayException as error:
            payload = u"Error: {}".format(error)
        row = [
            record._id,
            self._get_state(record)[1],
            self._get_person_id_link(record),
            record.url if record.url else _(u'Unable to generate url for record'),
            self._format_date(record.last_checked) if record.last_checked else '---',
            escape(record.failure_reason) if not record.succeeded else None,
            payload,
        ]
        return row

    def _get_person_id_link(self, record):
        try:
            person_id = get_person_case(self.domain, record.payload_id)
            return '<a href="{url}" target="_blank">{case_id}</a>'.format(
                url=reverse('case_details', args=[self.domain, person_id]),
                case_id=person_id
            )
        except ENikshayException as error:
            return u"Error: {}".format(error)
