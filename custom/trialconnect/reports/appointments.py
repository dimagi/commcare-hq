from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.sms.models import WORKFLOW_REMINDER
from corehq.elastic import es_query, ES_URLS
from corehq.pillows.sms import TC_STUB
from custom.trialconnect.reports import TrialConnectReport


class AppointmentsReport(TrialConnectReport):
    slug = 'appointments'
    name = ugettext_noop("Appointments")
    description = ugettext_noop("Description for Appointments Report")
    section_name = ugettext_noop("Appointments")
    fields = [
        'corehq.apps.reports.filters.select.MultiCaseGroupFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    def appointments_query(self, field_name, facets, check_response_state=False):
        q = self.base_query
        q["filter"] = {"and": [
            {"term": {"workflow": WORKFLOW_REMINDER.lower()}},
            {"term": {TC_STUB+field_name+'.case_type': 'cc_appointment'}},
        ]}
        if check_response_state:
            q["filter"]["and"].extend([{"term": {TC_STUB+field_name+'.response_state': 'confirmed'}}])
        facets = [TC_STUB+field_name+'.case_id']
        return es_query(q=q, es_url=ES_URLS['sms'], facets=facets, size=0)

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
        def unique(field_name, check_response_state=False):
            facets = {
                "case_data": TC_STUB+'case_data.case_id',
                "session_data": TC_STUB+'session_data.session_id'
            }
            data = self.appointments_query(field_name, [facets[field_name]], check_response_state)
            return len(data['facets'][facets[field_name]]['terms'])

        appointments_sent = unique('case_data')
        appointments_confirmed = unique('case_data', check_response_state=True)
        reminders_sent = unique('case_data')
        reminders_confirmed = unique('case_data', check_response_state=True)
        return [[
            appointments_sent,
            (float(appointments_confirmed)/appointments_sent) * 100 if appointments_sent else 'nan',
            (float(reminders_confirmed)/reminders_sent) * 100 if reminders_sent else 'nan',
            (float(reminders_sent)/appointments_sent) * 100 if appointments_sent else 'nan',
            (float(reminders_confirmed)/appointments_sent) * 100 if appointments_sent else 'nan',
        ]]
