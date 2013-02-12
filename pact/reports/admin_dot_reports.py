from datetime import datetime, timedelta
import uuid
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from pact.models import PactPatientCase, CObservation
from pact.reports.dot import PactDOTPatientField


class PactDOTAdminPatientField(PactDOTPatientField):
    slug = "dot_patient"
    name = "DOT Patient"
    default_option = "All Patients"


class PactDOTAdminReport(GenericTabularReport, CustomProjectReport):
    fields = ['pact.reports.admin_dot_reports.PactDOTAdminPatientField',
              'corehq.apps.reports.fields.DatespanField']
    name = "PACT DOT Admin"
    slug = "pactdotadmin"
    emailable = True
    exportable = True
    report_template_path = "pact/admin/pact_dot_admin.html"

    def tabular_data(self, mode, case_id, start_date, end_date):#, limit=50, skip=0):
        print "##########tabular data!"
        print case_id
        print mode
        print start_date
        print end_date
        try:
            case_doc = PactPatientCase.get(case_id)
            pactid = case_doc.pactid
            print "got casedoc and pactid"
        except:
            case_doc = None
            pactid = None

        if case_doc is not None:
            if mode == 'all':
                start_date = end_date - timedelta(1000)
                startkey = [case_id, 'anchor_date', start_date.year,
                            start_date.month, start_date.day]
                endkey = [case_id, 'anchor_date', end_date.year, end_date.month,
                          end_date.day]
                csv_filename = 'dots_csv_pt_%s.csv' % (pactid)
            else:
                startkey = [case_id, 'anchor_date', start_date.year,
                            start_date.month, start_date.day]
                endkey = [case_id, 'anchor_date', end_date.year, end_date.month,
                          end_date.day]
                csv_filename = 'dots_csv_pt_%s-%s_to_%s.csv' % (
                    pactid, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        elif case_doc is None:
            if mode == 'all':
                start_date = end_date - timedelta(1000)
                startkey = [start_date.year, start_date.month, start_date.day]
                endkey = [end_date.year, end_date.month, end_date.day]
                csv_filename = 'dots_csv_pt_all.csv'
            else:
                startkey = [start_date.year, start_date.month, start_date.day]
                endkey = [end_date.year, end_date.month, end_date.day]
                csv_filename = 'dots_csv_pt_all-%s_to_%s.csv' % (
                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                #heading
        print startkey
        print endkey
        view_results = CObservation.view('pact/dots_observations', startkey=startkey, endkey=endkey)#, limit=limit, skip=skip)

        for v in view_results:
            yield v

    @property
    def headers(self):
        #csv_keys = ['submitted_date', u'note', u'patient', 'doc_type', 'is_reconciliation', u'provider',  # u'day_index', 'day_note', u'encounter_date', u'anchor_date', u'total_doses',


        # u'pact_id', u'dose_number', u'created_date', u'is_art', u'adherence', '_id', u'doc_id', u'method', u'observed_date']
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
        start_date_str = self.request.GET.get('startdate', (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d'))
        end_date_str = self.request.GET.get('enddate', datetime.utcnow().strftime('%Y-%m-%d'))

        if case_id == '':
            mode = 'all'
            case_id = None
        else:
            mode = ''

        for num, obs in enumerate(self.tabular_data(mode, case_id, datetime.strptime(start_date_str, '%Y-%m-%d'), datetime.strptime(end_date_str, '%Y-%m-%d'))):#, limit=self.pagination.count, skip=self.pagination.start)):
            dict_obj = obs.to_json()
            row = [dict_obj[x.prop_name].encode('utf-8') if isinstance(dict_obj[x.prop_name], unicode) else dict_obj[x.prop_name] for x in self.headers]
            yield row

    @property
    def total_records(self):
        """
            Override for pagination.
            Returns an integer.
        """
        return 1000


    @property
    def shared_pagination_GET_params(self):
        """
        Override the params and applies all the params of the originating view to the GET
        so as to get sorting working correctly with the context of the GET params
        """
        ret = []
        for k, v in self.request.GET.items():
            ret.append(dict(name=k, value=v))
        return ret

