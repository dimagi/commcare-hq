from datetime import timedelta
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import LineChart
from corehq.apps.sms.models import WORKFLOW_REMINDER
from corehq.elastic import es_query, ES_URLS
from corehq.pillows.sms import TC_STUB
from corehq.util.dates import unix_time_millis
from custom.trialconnect.reports import TrialConnectReport

unix_time_millis

class AppointmentsReport(TrialConnectReport):
    slug = 'appointments'
    name = ugettext_noop("Appointments")
    description = ugettext_noop("Description for Appointments Report")
    section_name = ugettext_noop("Appointments")
    fields = [
        'corehq.apps.reports.filters.select.MultiCaseGroupFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    def appointments_query(self, field_name, facets, check_response_state=False, base_query=None):
        q = base_query or self.base_query
        q["filter"] = {"and": [
            {"term": {"workflow": WORKFLOW_REMINDER.lower()}},
            {"term": {TC_STUB+field_name+'.case_type': 'cc_appointment'}},
        ]}
        if check_response_state:
            q["filter"]["and"].extend([{"term": {TC_STUB+field_name+'.response_state': 'confirmed'}}])
        return es_query(q=q, es_url=ES_URLS['sms'], facets=facets, size=0)

    def unique(self, field_name, check_response_state=False, base_query=None):
        base_query = base_query or self.base_query
        facets = {
            "case_data": TC_STUB+'case_data.case_id',
            "session_data": TC_STUB+'session_data.session_id'
        }
        data = self.appointments_query(field_name, [facets[field_name]], check_response_state, base_query=base_query)
        return len(data['facets'][facets[field_name]]['terms'])

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Total Appointments Sent")),
            DataTablesColumn(_("% Appointments Confirmed")),
            DataTablesColumn(_("% Reminders Confirmed")),
            DataTablesColumn(_("Avg Reminders Per Appointment")),
            DataTablesColumn(_("Avg Confirmations Per Appointment")),
        )

    @property
    def rows(self):
        appointments_sent = self.unique('case_data')
        appointments_confirmed = self.unique('case_data', check_response_state=True)
        reminders_sent = self.unique('session_data')
        reminders_confirmed = self.unique('session_data', check_response_state=True)
        return [[
            appointments_sent,
            (float(appointments_confirmed)/appointments_sent) * 100 if appointments_sent else 'nan',
            (float(reminders_confirmed)/reminders_sent) * 100 if reminders_sent else 'nan',
            (float(reminders_sent)/appointments_sent) * 100 if appointments_sent else 'nan',
            (float(reminders_confirmed)/appointments_sent) * 100 if appointments_sent else 'nan',
        ]]

    def gen_base_query(self, start):
        start = start.strftime("%Y-%m-%d")
        q = self.base_query
        q["query"]["bool"]["must"][1]["range"]["date"]["from"] = start
        q["query"]["bool"]["must"][1]["range"]["date"]["to"] = start

    def percent_over_time(self, field_name):
        values = []
        start, end = self.datespan.startdate_utc, self.datespan.enddate_utc
        while start <= end:
            base_query = self.gen_base_query(start)
            num = self.unique(field_name, True, base_query=base_query)
            denom = self.unique(field_name, base_query=base_query)
            values.append({
                "x": int(unix_time_millis(start)),
                "y": float(num)/denom if denom != 0 else 0
            })
            start += timedelta(days=1)
        return values

    @property
    def charts(self):
        chart = LineChart(_("Appointment Reminders"), None, None)
        chart.data = [
            {
                "key": _("% Appointments Confirmed"),
                "values": self.percent_over_time('case_data'),
            },
            {
                "key": _("% Reminders Confirmed"),
                "values": self.percent_over_time('session_data'),
            },
        ]
        chart.x_axis_uses_dates = True
        return [chart]
