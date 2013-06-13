from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.couch.database import get_db
from hsph.reports import HSPHSiteDataMixin    
from django.utils.translation import ugettext as _
from datetime import date, timedelta

class DataSummaryReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    """
        Base class for this section
    """
    pass


class FacilityWiseFollowUpRepoert(GenericTabularReport, DataSummaryReport, 
                                                        HSPHSiteDataMixin):
    name = "Facility Wise Follow Up Report"
    slug = "hsph_facility_wise_follow_up"
    fields = ['corehq.apps.reports.fields.DatespanField',
               'corehq.apps.reports.fields.GroupField',
              'hsph.fields.NameOfFIDAField',
              'hsph.fields.SiteField']

    show_all_rows_option = True

    def _parse_date(self, date_str):
        y, m, d = [int(val) for val in date_str.split('-')]
        return date(y, m, d)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Region")),
            DataTablesColumn(_("District")),
            DataTablesColumn(_("Site")),
            DataTablesColumn(_("Fida Name")),
            DataTablesColumn(_("Births")),
            DataTablesColumn(_("Open Cases")),
            DataTablesColumn(_("Not Yet Open for Follow Up")),
            DataTablesColumn(_("Open for CATI Follow Up")),
            DataTablesColumn(_("Open for FADA Follow Up")),
            DataTablesColumn(_("TT Closed Cases")),
            DataTablesColumn(_("Followed Up By Call Center")),
            DataTablesColumn(_("Followed Up By Field")),
            DataTablesColumn(_("Lost to Follow Up")),

        )

    @property
    def rows(self):        
        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]

        all_keys = get_db().view('hsph/facility_wise_follow_up',
                    reduce=True,
                    group=True, group_level=4)

        rpt_keys = []
        key_start = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
            
        report_sites = self.generate_keys()
        for entry in all_keys:
            if entry['key'][0:3] in report_sites:
                if self.individual:
                    if entry['key'][-1] == self.individual:
                        rpt_keys.append(entry)
                elif self.user_ids:
                    if entry['key'][-1] in self.user_ids:
                        rpt_keys.append(entry)
                else:
                    rpt_keys = all_keys

        def get_view_results(case_type, start_dte, end_dte, reduce=True):
            my_start_key=key_start + [case_type] + [start_dte]
            if not start_dte:
                my_start_key = key_start + [case_type]
            data = get_db().view('hsph/facility_wise_follow_up',
                                 reduce=reduce,
                                 startkey=my_start_key,
                                 endkey=key_start + [case_type] + [end_dte]
            )
            
            if reduce:
                return sum([ item['value'] for item in data])
            return data

        rows = []
        today = date.today()
        for item in  rpt_keys:
            key_start = item['key']
            region_id, district_id, site_number, user_id = item['key']
            region_name = self.get_region_name(region_id)
            district_name = self.get_district_name(region_id, district_id)
            
            site_name = self.get_site_name(region_id, district_id,
                site_number)

            fida = self.usernames[user_id]
            births = get_view_results('births', startdate, enddate)
            open_cases = get_view_results('open_cases', startdate, enddate)
                        
            not_yet_open_for_follow_up = 0
            for v in get_view_results('needing_follow_up', startdate, enddate, False):
                if today < self._parse_date(v['key'][-1]) + timedelta(days=8):
                    not_yet_open_for_follow_up += 1

            open_for_cati_follow_up = 0
            #Not closed and if (date_admission + 8) <= today <= (date_admission + 21)
            for v in get_view_results('needing_follow_up', startdate, enddate, False):
                date_admission = self._parse_date(v['key'][-1])
                if (date_admission + timedelta(days=8)) <= today and\
                today <= (date_admission + timedelta(days=21)):
                    open_for_cati_follow_up += 1

            open_for_fada_follow_up = 0
            # Not closed and today > date_admission+21
            for v in get_view_results('needing_follow_up', startdate, enddate, False):
                if today > self._parse_date(v['key'][-1]) + timedelta(days=21):
                    open_for_fada_follow_up += 1

            closed_cases = get_view_results('closed_cases', startdate, enddate)

            lost_to_follow_up = get_view_results('lost_to_follow_up', startdate,
                                                                        enddate)

            followed_up_by_call_center = get_view_results(
                               'followed_up_by_call_center', startdate, enddate)
            followed_up_by_field = get_view_results('followed_up_by_field',
                                                             startdate, enddate)

            rows.append([region_name, district_name, site_name, fida, births,
            open_cases, not_yet_open_for_follow_up, open_for_cati_follow_up,
            open_for_fada_follow_up, closed_cases, followed_up_by_call_center,
            followed_up_by_field, lost_to_follow_up])
        return rows
    
