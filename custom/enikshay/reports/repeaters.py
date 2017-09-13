from datetime import datetime, timedelta

from django.conf import settings
from django.utils.html import escape
from django.utils.translation import ugettext as _
from django.urls import reverse

from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain, get_repeat_record_count
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
            record.url if record.url else _(u'Unable to generate url for record'),
            self._format_date(record.last_checked) if record.last_checked else '---',
            ",<br />".join(attempt_messages),
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
