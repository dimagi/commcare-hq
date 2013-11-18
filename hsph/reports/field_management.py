from collections import defaultdict
import datetime
import restkit.errors
import time
import numbers

from django.utils.datastructures import SortedDict
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.pillows.base import restore_property_dict

from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.reports.datatables import (DataTablesColumn, NumericColumn,
        DataTablesHeader)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports import util

from hsph.reports import HSPHSiteDataMixin
from hsph.fields import AllocatedToFilter, IHForCHFField, DCTLToFIDAFilter
from corehq.apps.api.es import ReportCaseES
from django.utils.translation import ugettext as _
from datetime import date, timedelta

def numeric_cell(val):
    if isinstance(val, numbers.Number):
        return util.format_datatables_data(text=val, sort_key=val)
    else:
        return val

def short_date_format(date):
    return date.strftime('%d-%b')

        
def datestring_minus_days(datestring, days):
    date = datetime.datetime.strptime(datestring[:10], '%Y-%m-%d')
    return (date - datetime.timedelta(days=days)).isoformat()

def get_user_site_map(domain):
    user_site_map = defaultdict(list)
    data_type = FixtureDataType.by_domain_tag(domain, 'site').first()
    fixtures = FixtureDataItem.by_data_type(domain, data_type.get_id)
    for fixture in fixtures:
        for user in fixture.get_users():
            user_site_map[user._id].append(fixture.fields_without_attributes['site_id'])
    return user_site_map


def get_facility_map(domain):
    from hsph.fields import FacilityField

    facilities = FacilityField.getFacilities(domain=domain)
    return dict([(facility.get('val'), facility.get('text'))
                for facility in facilities])


class FIDAPerformanceReport(GenericTabularReport, CustomProjectReport,
                            ProjectReportParametersMixin, DatespanMixin):
    """
    BetterBirth Shared Dropbox/Updated ICT package/Reporting Specs/FIDA Performance_v2.xls 
    """
    name = "FIDA Performance"
    slug = "hsph_fida_performance"
    
    fields = [
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.DatespanField',
        'hsph.fields.DCTLToFIDAFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name of FIDA"),
            DataTablesColumn("Name of Team Leader"),
            NumericColumn("No. of Facilities Covered"),
            NumericColumn("No. of Facility Visits"),
            NumericColumn("No. of Facilities with less than 2 visits/week"),
            DataTablesColumn("Average Time per Birth Record"),
            NumericColumn("Average Number of Birth Records Uploaded Per Visit"),
            NumericColumn("No. of Births with no phone details"),
            NumericColumn("No. of Births with no address"),
            NumericColumn("No. of Births with no contact info"),
            NumericColumn("No. of Home Visits assigned"),
            NumericColumn("No. of Home Visits completed"),
            NumericColumn("No. of Home Visits completed per day"),
            NumericColumn("No. of Home Visits Open at 30 Days"))

    @property
    def rows(self):
        user_data = DCTLToFIDAFilter.get_user_data(
                self.request_params, domain=self.domain)
        self.override_user_ids = user_data['leaf_user_ids']

        user_site_map = get_user_site_map(self.domain)

        # ordered keys with default values
        keys = SortedDict([
            ('fidaName', None),
            ('teamLeaderName', None),
            ('facilitiesCovered', 0),
            ('facilityVisits', 0),
            ('facilitiesVisitedLessThanTwicePerWeek', None),
            ('avgBirthRegistrationTime', None),
            ('birthRegistrationsPerVisit', None),
            ('noPhoneDetails', 0),
            ('noAddress', 0),
            ('noContactInfo', 0),
            ('homeVisitsAssigned', 0),
            ('homeVisitsCompleted', 0),
            ('homeVisitsCompletedPerDay', 0),
            ('homeVisitsOpenAt30Days', 0)
        ])

        rows = []
        db = get_db()

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]
        
        to_date = lambda string: datetime.datetime.strptime(
                        string, "%Y-%m-%d").date()
        weeks = (to_date(enddate) - to_date(startdate)).days // 7

        for user in self.users:
            user_id = user.get('user_id')

            row = db.view('hsph/fida_performance',
                startkey=["all", self.domain, user_id, startdate],
                endkey=["all", self.domain, user_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

            workingDays = db.view('hsph/fida_performance',
                startkey=["workingDays", self.domain, user_id, startdate],
                endkey=["workingDays", self.domain, user_id, enddate],
                reduce=False,
                wrapper=lambda r: r['value']['workingDay']).all()
            workingDays = set(workingDays)

            row['fidaName'] = self.table_cell(
                    user.get('raw_username'), user.get('username_in_report'))

            dctl = user_data['user_parent_map'][user['user_id']]
            row['teamLeaderName'] = self.table_cell(
                    dctl.raw_username,
                    dctl.username_in_report)
            row['facilitiesCovered'] = len(user_site_map[user_id])
            row['facilitiesVisitedLessThanTwicePerWeek'] = len(
                filter(
                    lambda count: count < weeks * 2, 
                    [row.get(site_id + 'Visits', 0) 
                     for site_id in user_site_map[user_id]]
                )
            )
            if row.get('avgBirthRegistrationTime'):
                row['avgBirthRegistrationTime'] = time.strftime(
                        '%M:%S', time.gmtime(row['avgBirthRegistrationTime']))
            else:
                row['avgBirthRegistrationTime'] = None

            if workingDays:
                row['homeVisitsCompletedPerDay'] = round(
                        row.get('homeVisitsCompleted', 0) / float(len(workingDays)), 1)
            else:
                row['homeVisitsCompletedPerDay'] = 0.0

            # These queries can fail if startdate is less than N days before
            # enddate.  We just catch and supply a default value.
            try:
                row['homeVisitsAssigned'] = db.view('hsph/fida_performance',
                    startkey=['assigned', self.domain, user_id, startdate],
                    endkey=['assigned', self.domain, user_id,
                        datestring_minus_days(enddate, 21)],
                    reduce=True,
                    wrapper=lambda r: r['value']['homeVisitsAssigned']
                ).first()
            except restkit.errors.RequestFailed:
                row['homeVisitsAssigned'] = 0

            try:
                row['homeVisitsOpenAt30Days'] = db.view('hsph/fida_performance',
                    startkey=['open30Days', self.domain, user_id, startdate],
                    endkey=['open30Days', self.domain, user_id,
                        datestring_minus_days(enddate, 29)],
                    reduce=True,
                    wrapper=lambda r: r['value']['homeVisitsOpenAt30Days']
                ).first()
            except restkit.errors.RequestFailed:
                row['homeVisitsOpenAt30Days'] = 0

            list_row = []
            for k, v in keys.items():
                val = row.get(k, v)
                if val is None:
                    val = '---'
                list_row.append(numeric_cell(val))

            rows.append(list_row)

        return rows


class FacilityRegistrationsReport(GenericTabularReport, CustomProjectReport,
                                  ProjectReportParametersMixin, DatespanMixin,
                                  HSPHSiteDataMixin):
    """
    BetterBirth Shared Dropbox/Updated ICT package/Reporting Specs/Facility
    Registrations_v2_ss.xls
    """
    name = "Facility Registrations"
    slug = "hsph_facility_registrations"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.DCTLToFIDAFilter',
              'hsph.fields.SiteField']

    @property
    @memoized
    def facility_name_map(self):
        from hsph.fields import FacilityField

        facilities = FacilityField.getFacilities(domain=self.domain)
        return dict([(facility.get('val'), facility.get('text'))
                     for facility in facilities])
    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Facility"),
            DataTablesColumn("FIDA"),
            DataTablesColumn("Team Leader"),
            NumericColumn("No. of visits by FIDA"),
            NumericColumn("No. of birth registrations"),
            NumericColumn("No. of births with no phone details"),
            NumericColumn("No. of births with no address"),
            NumericColumn("No. of births with no contact info"))

    @property
    def rows(self):
        user_data = DCTLToFIDAFilter.get_user_data(
                self.request_params, domain=self.domain)
        self.override_user_ids = user_data['leaf_user_ids']

        db = get_db()
        site_map = self.selected_site_map or self.site_map
       
        # hack
        facilities = IHForCHFField.get_selected_facilities(
                site_map, domain=self.domain)
        facilities = facilities['ihf'] + facilities['chf']

        rows = []

        for user in self.users:
            for site_id in facilities:
                key = [self.domain, user.get('user_id'), site_id]
                data = db.view('hsph/facility_registrations',
                    startkey=key + [self.datespan.startdate_param_utc],
                    endkey=key + [self.datespan.enddate_param_utc],
                    reduce=True,
                    wrapper=lambda r: r['value']
                ).first()
                
                if data:
                    dctl = user_data['user_parent_map'][user['user_id']]
                    rows.append([
                        self.facility_name_map[site_id],
                        self.table_cell(
                            user.get('raw_username'),
                            user.get('username_in_report')),
                        self.table_cell(
                            dctl.raw_username,
                            dctl.username_in_report),
                        numeric_cell(data.get('facilityVisits', 0)),
                        numeric_cell(data.get('birthRegistrations', 0)),
                        numeric_cell(data.get('noPhoneDetails', 0)),
                        numeric_cell(data.get('noAddress', 0)),
                        numeric_cell(data.get('noContactInfo', 0)),
                    ])

        return rows


class HSPHCaseDisplay(CaseDisplay):

    @property
    @memoized
    def _date_admission(self):
        return self.parse_date(self.case['date_admission'])

    @property
    def region(self):
        try:
            return self.report.get_region_name(self.case['region_id'])
        except AttributeError:
            return ""

    @property
    def district(self):
        try:
            return self.report.get_district_name(
                self.case['region_id'], self.case['district_id'])
        except AttributeError:
            return ""

    @property
    def site(self):
        try:
            return self.report.get_site_name(
                self.case['region_id'], self.case['district_id'],
                self.case['site_number'])
        except AttributeError:
            return ""

    @property
    def patient_id(self):
        return self.case.get('patient_id', '')

    @property
    def status(self):
        return "Closed" if self.case['closed'] else "Open"

    @property
    def mother_name(self):
        return self.case.get('name_mother', '')

    @property
    def date_admission(self):
        return short_date_format(self._date_admission)

    @property
    def address(self):
        return self.case.get('house_address', '')

    @property
    @memoized
    def allocated_to(self):
        # this logic is duplicated for elasticsearch in CaseReport.case_filter
        UNKNOWN = "Unknown"
        CALL_CENTER = "Call Center"
        FIELD = "Field"

        if self.case['closed']:
            if 'closed_by' not in self.case:
                return UNKNOWN

            if self.case['closed_by'] in ("cati", "cati_tl"):
                return CALL_CENTER
            elif self.case['closed_by'] in ("fida", "field_manager"):
                return FIELD
            else:
                return UNKNOWN
        else:
            today = datetime.datetime.now()
            if today <= self._date_admission + datetime.timedelta(days=21):
                return CALL_CENTER
            else:
                return FIELD
    
    @property
    def allocated_start(self):
        try:
            delta = datetime.timedelta(
                    days=8 if self.allocated_to == "Call Center" else 21)
            return short_date_format(self._date_admission + delta)
        except AttributeError:
            return ""

    @property
    def allocated_end(self):
        try:
            delta = datetime.timedelta(
                    days=20 if self.allocated_to == 'Call Center' else 29)
            return short_date_format(self._date_admission + delta)
        except AttributeError:
            return ""

    @property
    def outside_allocated_period(self):
        if self.case['closed_on']:
            compare_date = self.parse_date(
                    self.case['closed_on']).replace(tzinfo=None)
        else:
            compare_date = datetime.datetime.utcnow().replace(tzinfo=None)

        return 'Yes' if (compare_date - self._date_admission).days > 29 else 'No'


class CaseReport(CaseListReport, CustomProjectReport, HSPHSiteDataMixin,
                 DatespanMixin):
    name = 'Case Report'
    slug = 'case_report'
    
    fields = (
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.DatespanField',
        'hsph.fields.SiteField',
        'hsph.fields.AllocatedToFilter',
        'hsph.fields.DCTLToFIDAFilter',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    )

    default_case_type = 'birth'

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("Patient ID"),
            DataTablesColumn("Status"),
            DataTablesColumn("Mother Name"),
            DataTablesColumn("Date of Admission"),
            DataTablesColumn("Address of Patient"),
            DataTablesColumn("Allocated To"),
            DataTablesColumn("Allocated Start"),
            DataTablesColumn("Allocated End"),
            DataTablesColumn("Outside Allocated Period")
        )
        headers.no_sort = True
        return headers

    @property
    def case_filter(self):
        allocated_to = self.request_params.get(AllocatedToFilter.slug, '')
        region_id = self.request_params.get('hsph_region', '')
        district_id = self.request_params.get('hsph_district', '')
        site_num = str(self.request_params.get('hsph_site', ''))

        filters = [{
            'range': {
                'opened_on': {
                    "from": self.datespan.startdate_param_utc,
                    "to": self.datespan.enddate_param_utc
                }
            }
        }]

        if site_num:
            filters.append({'term': {'site_number.#value': site_num.lower()}})
        if district_id:
            filters.append({'term': {'district_id.#value': district_id.lower()}})
        if region_id:
            filters.append({'term': {'region_id.#value': region_id.lower()}})

        if allocated_to:
            max_date_admission = (datetime.date.today() -
                datetime.timedelta(days=21)).strftime("%Y-%m-%d")

            call_center_filter = {
                'or': [
                    {'and': [
                        {'term': {'closed': True}},
                        {'prefix': {'closed_by': 'cati'}}
                    ]},
                    {'and': [
                        {'term': {'closed': False}},
                        {'range': {
                            'date_admission.#value': {
                                'from': max_date_admission
                            }
                        }}
                    ]}
                ]
            }

            if allocated_to == 'cati':
                filters.append(call_center_filter)
            else:
                filters.append({'not': call_center_filter})

        return {'and': filters} if filters else {}

    @property
    def shared_pagination_GET_params(self):
        user_data = DCTLToFIDAFilter.get_user_data(
                self.request_params, domain=self.domain)
        self.override_user_ids = user_data['leaf_user_ids']
        params = super(CaseReport, self).shared_pagination_GET_params

        slugs = [
            AllocatedToFilter.slug,
            'hsph_region',
            'hsph_district',
            'hsph_site',
            'startdate',
            'enddate'
        ]

        for slug in slugs:
            params.append({
                'name': slug,
                'value': self.request_params.get(slug, '')
            })

        return params

    @property
    def rows(self):
        case_displays = (HSPHCaseDisplay(self, restore_property_dict(self.get_case(case)))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.region,
                disp.district,
                disp.site,
                disp.patient_id,
                disp.status,
                disp.case_link,
                disp.date_admission,
                disp.address,
                disp.allocated_to,
                disp.allocated_start,
                disp.allocated_end,
                disp.outside_allocated_period,
            ]


class FacilityWiseFollowUpReport(GenericTabularReport, DatespanMixin,
                                 HSPHSiteDataMixin, CustomProjectReport,
                                 ProjectReportParametersMixin):
    name = "Facility Wise Follow Up Report"
    slug = "hsph_facility_wise_follow_up"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.DCTLToFIDAFilter',
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
        user_data = DCTLToFIDAFilter.get_user_data(
                self.request_params, domain=self.domain)
        self.override_user_ids = user_data['leaf_user_ids']

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]

        all_keys = get_db().view('hsph/facility_wise_follow_up',
                    reduce=True,
                    group=True, group_level=5)

        rpt_keys = []
        key_start = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map

        facility_map = get_facility_map(self.domain)

        # make sure key elements are strings
        report_sites =  [[str(item) for item in rk] for rk in self.generate_keys()]

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

        def get_view_results(case_type, start_dte, end_dte):
            my_start_key=key_start + [case_type] + [start_dte]
            if not start_dte:
                my_start_key = key_start + [case_type]
            data = get_db().view('hsph/facility_wise_follow_up',
                                 reduce=True,
                                 startkey=my_start_key,
                                 endkey=key_start + [case_type] + [end_dte]
            )

            return sum([ item['value'] for item in data])

        rows = []
        today = date.today()
        for item in rpt_keys:
            key_start = item['key']
            region_id, district_id, site_number, site_id, user_id = item['key']
            region_name = self.get_region_name(region_id)
            district_name = self.get_district_name(region_id, district_id)
            site_name = facility_map.get(site_id, site_id)
            fida = self.usernames.get(user_id, "")
            births = get_view_results('births', startdate, enddate)
            open_cases = get_view_results('open_cases', startdate, enddate)

            # Not closed and If today < date_admission + 8
            start = today - timedelta(days=7)
            not_yet_open_for_follow_up = get_view_results('needing_follow_up',
                start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))

            # Not closed and if (date_admission + 8) <= today <= (date_admission + 21)
            start = today - timedelta(days=21)
            end = today - timedelta(days=8)
            open_for_cati_follow_up = get_view_results('needing_follow_up',
                start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))

            # Not closed and today > date_admission+21
            end = today - timedelta(days = 22)
            open_for_fada_follow_up = get_view_results('needing_follow_up',
                "", end.strftime('%Y-%m-%d'))

            closed_cases = get_view_results('closed_cases', startdate, enddate)

            lost_to_follow_up = get_view_results('lost_to_follow_up', startdate, enddate)

            followed_up_by_call_center = get_view_results(
                'followed_up_by_call_center', startdate, enddate)
            followed_up_by_field = get_view_results('followed_up_by_field',
                startdate, enddate)

            rows.append([region_name, district_name, site_name, fida, births,
                open_cases, not_yet_open_for_follow_up, open_for_cati_follow_up,
                open_for_fada_follow_up, closed_cases, followed_up_by_call_center,
                followed_up_by_field, lost_to_follow_up])

        return rows
