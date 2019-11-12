from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.users.models import CommCareUser
from dimagi.utils.parsing import json_format_date
from pact.enums import PACT_DOMAIN
from pact.reports import chw_schedule


class PactCHWAdminReport(GenericTabularReport, CustomProjectReport):
    fields = [
        'corehq.apps.reports.filters.users.SelectMobileWorkerFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]
    name = "PACT CHW Admin"
    slug = "pactchwadmin"
    emailable = True
    exportable = True
    report_template_path = "pact/admin/pact_chw_schedule_admin.html"

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Scheduled Date"),
            DataTablesColumn("CHW Scheduled"),
            DataTablesColumn("Patient"),
            DataTablesColumn("Scheduled"),
            DataTablesColumn("Visit Kept"),
            DataTablesColumn("Type"),
            DataTablesColumn("Contact"),
            DataTablesColumn("CHW Visited"),
            DataTablesColumn("Observed ART"),
            DataTablesColumn("Pillbox Check"),
            DataTablesColumn("Doc ID"),
        )
        return headers

    def csv_data_block(self, username, user_context):
        """
        generator of rows of scheduled visits for a given chw
        """
        def finish_row_blanks(r):
            if len(r) < 11:
                for x in range(11 - len(r)):
                    r.append('---')
            return r
        # {% for visit_date, patient_visits in date_arr %}
        # {% if patient_visits %}
        # {% for cpatient, visit in patient_visits %}
        # {% if visit %}

        #this is ugly, but we're repeating the work of the template for rendering the row data
        for visit_date, patient_visits in user_context['date_arr']:
            rowdata = []
            if len(patient_visits) > 0:
                for patient_case, visit in patient_visits:
                    rowdata = [json_format_date(visit_date), username,
                               patient_case['pactid']]
                    if visit is not None:
                        ####is scheduled
                        if visit.get('scheduled', '---') == 'yes':
                            rowdata.append('scheduled')
                        else:
                            rowdata.append('unscheduled')

                        ####visit kept
                        visit_kept = visit.get('visit_kept', '---')
                        if visit_kept == 'notice':
                            rowdata.append("no - notice given")
                        elif visit_kept == 'yes':
                            rowdata.append("yes")
                        else:
                            rowdata.append(visit_kept)

                        #visit type
                        rowdata.append(visit.get('visit_type', '---'))

                        #contact type
                        rowdata.append(visit.get('contact_type', '---'))

                        rowdata.append(visit.get('username', '---'))
                        rowdata.append(visit.get('observed_art', '---'))
                        rowdata.append(visit.get('has_pillbox_check', '---'))
                        rowdata.append(visit.get('doc_id', '---'))
                    else:
                        rowdata.append('novisit')
                    yield finish_row_blanks(rowdata)
            # else:
            #     no patients scheduled, skipping day altogether - matches chw schedule view
                # nopatient_row = [json_format_date(visit_date), username, 'nopatient']
                # yield finish_row_blanks(nopatient_row)

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        user_id = self.request.GET.get('individual', None)

        if user_id is None or user_id == '':
            #all users
            user_docs = CommCareUser.by_domain(PACT_DOMAIN)
        else:
            user_docs = [CommCareUser.get(user_id)]

        for user_doc in user_docs:
            scheduled_context = chw_schedule.chw_calendar_submit_report(self.request, user_doc.raw_username)
            for row in self.csv_data_block(user_doc.raw_username, scheduled_context):
                yield row
