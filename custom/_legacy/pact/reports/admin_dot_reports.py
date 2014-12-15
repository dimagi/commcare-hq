from datetime import datetime, timedelta
import logging
import uuid
from couchdbkit import ResourceNotFound
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from pact.models import PactPatientCase, CObservation
from pact.reports.dot import PactDOTPatientField


class PactDOTAdminPatientField(PactDOTPatientField):
    slug = "dot_patient"
    name = "DOT Patient"
    default_option = "All Patients"

COUCH_CHUNK_LIMIT = 500
COUCH_MAX_LIMIT = 1000

class PactDOTAdminReport(GenericTabularReport, CustomProjectReport):
    fields = ['pact.reports.admin_dot_reports.PactDOTAdminPatientField',
              'corehq.apps.reports.filters.dates.DatespanFilter']
    name = "PACT DOT Admin"
    slug = "pactdotadmin"
    emailable = True
    exportable = True
    report_template_path = "pact/admin/pact_dot_admin.html"

    def tabular_data(self, mode, case_id, start_date, end_date):#, limit=50, skip=0):
        try:
            case_doc = PactPatientCase.get(case_id)
        except ResourceNotFound:
            case_doc = None

        if case_doc is not None:
            # patient is selected
            startkey = [case_id, 'anchor_date', start_date.year, start_date.month, start_date.day]
            endkey = [case_id, 'anchor_date', end_date.year, end_date.month, end_date.day]
        elif case_doc is None:
            # patient is not selected, do all patients
            startkey = [start_date.year, start_date.month, start_date.day]
            endkey = [end_date.year, end_date.month, end_date.day]
        skip = 0
        view_results = CObservation.view(
            'pact/dots_observations',
            startkey=startkey,
            endkey=endkey,
            limit=COUCH_CHUNK_LIMIT,
            skip=skip,
            classes={None: CObservation},
        ).all()
        while len(view_results) > 0:
            if skip > COUCH_MAX_LIMIT:
                logging.error("Pact DOT admin query: Too much data returned for query %s-%s" % (startkey, endkey))
                break
            for v in view_results:
                yield v
            skip += COUCH_CHUNK_LIMIT
            view_results = CObservation.view(
                'pact/dots_observations',
                startkey=startkey,
                endkey=endkey,
                limit=COUCH_CHUNK_LIMIT,
                skip=skip,
                classes={None: CObservation},
            ).all()

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("PACT ID", prop_name="pact_id"),
            DataTablesColumn("ART", prop_name="is_art"),
            DataTablesColumn("CHW", prop_name="provider"),
            DataTablesColumn("Method", prop_name="method"),
            DataTablesColumn("Encounter Date", prop_name="encounter_date"),
            DataTablesColumn("Anchor Date", prop_name="anchor_date"),
            DataTablesColumn("Observed Date", prop_name="observed_date"),
            DataTablesColumn("Adherence", prop_name="adherence"),
            DataTablesColumn("Created Date", prop_name="created_date"),
            DataTablesColumn("Submitted Date", prop_name="submitted_date"),
            DataTablesColumn("Dose Number", prop_name="dose_number"),
            DataTablesColumn("Total Doses", prop_name="total_doses"),
            DataTablesColumn("Day Slot", prop_name="day_slot"),
            DataTablesColumn("Note", prop_name="note")
        )
        return headers

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        case_id = self.request.GET.get('dot_patient', '')
        start_date_str = self.request.GET.get('startdate',
                                              (datetime.utcnow() - timedelta(days=7)).strftime(
                                                  '%Y-%m-%d'))
        end_date_str = self.request.GET.get('enddate', datetime.utcnow().strftime('%Y-%m-%d'))

        if case_id == '':
            mode = 'all'
        else:
            mode = ''

        for num, obs in enumerate(self.tabular_data(mode, case_id, datetime.strptime(start_date_str, '%Y-%m-%d'), datetime.strptime(end_date_str, '%Y-%m-%d'))):
            dict_obj = obs.to_json()
            row = [dict_obj[x.prop_name].encode('utf-8') if isinstance(dict_obj[x.prop_name], unicode) else dict_obj[x.prop_name] for x in self.headers]
            yield row
