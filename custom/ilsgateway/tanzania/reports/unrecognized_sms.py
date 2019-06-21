from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqwebapp.doc_info import get_doc_info
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.sms.models import WORKFLOW_DEFAULT, SMS, INCOMING, OUTGOING
from corehq.apps.users.models import CouchUser
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from django.utils.translation import ugettext as _


# copy paste from: https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reports/standard/sms.py
# we can't extend report by MessageLogReport.
def _fmt(val):
    if val is None:
        return format_datatables_data("-", "-")
    else:
        return format_datatables_data(val, val)


class UnrecognizedSMSReport(CustomProjectReport, ProjectReportParametersMixin,
                            GenericTabularReport, DatespanMixin):
    name = ugettext_noop('Unrecognized SMS')
    slug = 'unrecognized_sms'
    fields = [AsyncLocationFilter, DatespanFilter]
    exportable = True

    def _fmt_timestamp(self, timestamp):
        return self.table_cell(
            timestamp,
            timestamp.strftime(SERVER_DATETIME_FORMAT),
        )

    def _fmt_contact_link(self, msg, doc_info):
        if doc_info:
            username, contact_type, url = (doc_info.display,
                doc_info.type_display, doc_info.link)
        else:
            username, contact_type, url = (None, None, None)
        username = username or "-"
        contact_type = contact_type or _("Unknown")
        if url:
            ret = self.table_cell(username, '<a href="%s">%s</a>' % (url, username))
        else:
            ret = self.table_cell(username, username)
        ret['raw'] = "|||".join([username, contact_type,
            msg.couch_recipient or ""])
        return ret

    def get_recipient_info(self, message, contact_cache):
        recipient_id = message.couch_recipient

        if recipient_id in contact_cache:
            return contact_cache[recipient_id]

        doc = None
        if recipient_id not in [None, ""]:
            try:
                if message.couch_recipient_doc_type == "CommCareCase":
                    doc = CommCareCase.get(recipient_id)
                else:
                    doc = CouchUser.get_by_user_id(recipient_id)
            except Exception:
                pass

        if doc:
            doc_info = get_doc_info(doc.to_json(), self.domain)
        else:
            doc_info = None

        contact_cache[recipient_id] = doc_info

        return doc_info

    @property
    def export_table(self):
        result = super(UnrecognizedSMSReport, self).export_table
        table = result[0][1]
        table = list(table)
        table[0].append(_("Contact Type"))
        table[0].append(_("Contact Id"))
        for row in table[1:]:
            contact_info = row[1].split("|||")
            row[1] = contact_info[0]
            row.append(contact_info[1])
            row.append(contact_info[2])
        result[0][1] = table
        return result

    def get_location_filter(self):
        locations = []
        location_id = AsyncLocationFilter.get_value(self.request, self.domain)
        if location_id:
            locations = SQLLocation.objects.get(
                location_id=location_id
            ).get_descendants(
                include_self=True
            ).filter(
                location_type__administrative=False
            ).values_list('location_id', flat=True)

        return locations

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn(_("Timestamp")),
            DataTablesColumn(_("User Name")),
            DataTablesColumn(_("Phone Number")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("Message")),
        )
        header.custom_sort = [[0, 'desc']]
        return header

    @property
    def rows(self):
        data = SMS.by_domain(
            self.domain,
            start_date=self.datespan.startdate_utc,
            end_date=self.datespan.enddate_utc
        ).filter(
            workflow__iexact=WORKFLOW_DEFAULT
        ).exclude(
            direction=OUTGOING,
            processed=False,
        ).order_by('date')
        result = []

        direction_map = {
            INCOMING: _("Incoming"),
            OUTGOING: _("Outgoing"),
        }
        reporting_locations_id = self.get_location_filter()

        contact_cache = {}
        for message in data:
            if reporting_locations_id and message.location_id not in reporting_locations_id:
                continue

            doc_info = self.get_recipient_info(message, contact_cache)
            phone_number = message.phone_number
            timestamp = ServerTime(message.date).user_time(self.timezone).done()
            result.append([
                self._fmt_timestamp(timestamp),
                self._fmt_contact_link(message, doc_info),
                _fmt(phone_number),
                _fmt(direction_map.get(message.direction, "-")),
                _fmt(message.text)
            ])

        return result
