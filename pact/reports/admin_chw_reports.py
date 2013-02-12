from datetime import datetime, timedelta
import uuid
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.users.models import CommCareUser
from pact.enums import PACT_DOMAIN
from pact.models import PactPatientCase, CObservation
from pact.reports import chw_schedule
from pact.reports.dot import PactDOTPatientField


class PactCHWAdminReport(GenericTabularReport, CustomProjectReport):
    fields = ['corehq.apps.reports.fields.SelectMobileWorkerField',  'corehq.apps.reports.fields.DatespanField']
    name = "PACT CHW Admin"
    slug = "pactchwadmin"
    emailable = True
    exportable = True
    report_template_path = "pact/admin/pact_chw_schedule_admin.html"

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
        headers = DataTablesHeader(
            DataTablesColumn("Patient"),
            DataTablesColumn("Scheduled"),
            DataTablesColumn("Visit Kept"),
            DataTablesColumn("Type"),
            DataTablesColumn("Contact"),
            DataTablesColumn("Observed ART"),
            DataTablesColumn("Pillbox Check"),
        )
        return headers

    @property
    def rows(self):
        """
            Override this method to create a functional tabular report.
            Returns 2D list of rows.
            [['row1'],[row2']]
        """
        user_id = self.request.GET.get('individual', None)

        if user_id is None:
            #all users
            user_docs = CommCareUser.by_domain(PACT_DOMAIN)
        else:
            user_docs = [CommCareUser.get(user_id)]

        for user_doc in user_docs:
            start_date_str = self.request.GET.get('startdate', (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d'))
            end_date_str = self.request.GET.get('enddate', datetime.utcnow().strftime('%Y-%m-%d'))
            scheduled_context = chw_schedule.chw_calendar_submit_report(self.request, user_doc.raw_username)
        yield []




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

