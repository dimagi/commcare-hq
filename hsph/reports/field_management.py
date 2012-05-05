import datetime
import dateutil
import pytz
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from corehq.apps.reports import util
from hsph.fields import FacilityField, NameOfDCTLField, SiteField, SelectCaseStatusField

class HSPHSiteDataMixin:
    request = None

    def generate_sitemap(self):
        self.site_map = SiteField.getSites()
        self.selected_site_map = {}

        region = self.request.GET.get(SiteField.slugs['region'], None)
        district = self.request.GET.get(SiteField.slugs['district'], None)
        site = self.request.GET.get(SiteField.slugs['site'], None)

        if region:
            self.selected_site_map[region] = self.site_map[region]
            if district:
                self.selected_site_map[region] = {}
                self.selected_site_map[region][district] = self.site_map[region][district]
                if site:
                    self.selected_site_map[region][district] = {}
                    self.selected_site_map[region][district][site] = self.site_map[region][district][site]


class HSPHFieldManagementReport(StandardTabularHQReport, StandardDateHQReport):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField']
    dctl_list = NameOfDCTLField.dctl_list

    def get_parameters(self):
        selected_dctl = self.request.GET.get(NameOfDCTLField.slug, '')
        if selected_dctl:
            self.dctl_list = [selected_dctl]

class DCOActivityReport(HSPHFieldManagementReport):
    name = "DCO Activity Report"
    slug = "hsph_dco_activity"

    def get_headers(self):
        return ["Name of DCO",
                "Name of DCTL",
                "No. Facilities Covered",
                "No. of Facility Visits",
                "No. of Facility Visits with less than 2 visits/week",
                "No. of Births Recorded",
                "Average time per Birth Record (min)",
                "No. of Home Visits assigned",
                "No. of Home Visits completed",
                "No. of Home Visits open at 21 days"]

    def get_rows(self):
        rows = []
        for user in self.users:
            for dctl in self.dctl_list:
                key = [user.userID, dctl]
                num_facilities = 0
                num_fac_visits = 0
                num_fac_visits_lt2 = 0
                num_births = 0
                avg_time = "---"
                num_home_assigned = 0
                num_home_completed = 0
                num_home_21days = 0

                data = get_db().view('hsph/field_dco_activity',
                    startkey = key + [self.datespan.startdate_param_utc],
                    endkey = key + [self.datespan.enddate_param_utc],
                    reduce = True
                ).first()

                if data:
                    data = data.get('value', {})
                    num_facilities = data.get('numFacilitiesVisited', 0)
                    num_fac_visits = data.get('numFacilityVisits', 0)
                    num_fac_visits_lt2 = data.get('lessThanTwoWeeklyFacilityVisits', 0)
                    num_births = data.get('totalBirths', 0)
                    reg_length = data.get('averageRegistrationLength', None)
                    if reg_length:
                        reg_length = datetime.datetime.fromtimestamp(reg_length//1000)
                        avg_time = reg_length.strftime("%M:%S")
                    num_home_assigned = data.get('numHomeVisits', 0)
                    num_home_completed = data.get('numHomeVisitsCompleted', 0)
                    num_home_21days = data.get('numHomeVisitsOpenAt21', 0)
                rows.append([
                    util.format_datatables_data(user.username_in_report, user.raw_username),
                    dctl,
                    num_facilities,
                    num_fac_visits,
                    num_fac_visits_lt2,
                    num_births,
                    avg_time,
                    num_home_assigned,
                    num_home_completed,
                    num_home_21days
                ])
        return rows


class FieldDataCollectionActivityReport(HSPHFieldManagementReport):
    name = "Field Data Collection Activity Report"
    slug = "hsph_field_data"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.FacilityField']

    def get_headers(self):
        return ["Facility Name",
                "Name of DCO",
                "Name of DCTL",
                "No. of visits by DCO",
                "No. of births recorded",
                "No. of births without contact details"]

    def get_parameters(self):
        super(FieldDataCollectionActivityReport, self).get_parameters()
        selected_fac = self.request.GET.get(FacilityField.slug, '')
        if selected_fac:
            self.facilities = [selected_fac]
        else:
            self.facilities = FacilityField.getFacilties()

    def get_rows(self):
        rows = []
        for user in self.users:
            for facility in self.facilities:
                for dctl in self.dctl_list:
                    key = [facility, user.userID, dctl]
                    data = get_db().view('hsph/field_data_collection_activity',
                            startkey = key + [self.datespan.startdate_param_utc],
                            endkey = key + [self.datespan.enddate_param_utc],
                            reduce = True
                        ).first()
                    if data:
                        data = data['value']
                        num_visits = data.get('numFacilityVisits', 0)
                        num_births = data.get('totalBirths', 0)
                        num_births_no_contact = data.get('totalBirthsWithoutContact', 0)
                        rows.append([
                            facility,
                            util.format_datatables_data(user.username_in_report, user.raw_username),
                            dctl,
                            num_visits,
                            num_births,
                            num_births_no_contact
                        ])

        return rows


class HVFollowUpStatusReport(HSPHFieldManagementReport, HSPHSiteDataMixin):
    name = "Home Visit Follow Up Status"
    slug = "hsph_hv_status"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        super(HVFollowUpStatusReport, self).get_parameters()
        self.generate_sitemap()

    def get_data(self, key, reduce=True):
        return get_db().view("hsph/field_follow_up_status",
            reduce=reduce,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc]
        ).all()

    def get_hv_range(self, original_key, dates=None):
        if not dates:
            dates = [0,8]
        key = [original_key[1], original_key[3], original_key[4], original_key[5]]
        now = self.datespan.enddate
        stop = now-datetime.timedelta(days=dates[0])
        stop = stop.strftime("%Y-%m-%d")
        last_day = dates[1]
        if last_day < 0:
            start = None
        else:
            start = now-datetime.timedelta(days=dates[1])
            start = start.strftime("%Y-%m-%d")
        data = get_db().view("hsph/home_visits_by_birth",
                                reduce=True,
                                startkey=key+[start],
                                endkey=key+[stop]
                            ).first()
        return data.get('value', 0) if data else 0

    def get_headers(self):
        return ["Region",
                "District",
                "Site",
                "DCO Name",
                "No. Births Recorded",
                "No. patients followed up by call center",
                "No. patients followed up by DCO center",
                "No. patients not yet open for follow up (<8 days)",
                "No. patients open for DCC follow up (<14 days)",
                "No. patients open for DCO follow up (>21 days)"]

    def get_rows(self):
        rows = []
        usernames = dict([(user.userID, util.format_datatables_data(user.username_in_report, user.raw_username)) for user in self.users ])

        if not self.selected_site_map:
            self.selected_site_map = self.site_map

        keys = [["by_site", user.userID, dctl, region, district, site]
                            for user in self.users
                            for dctl in self.dctl_list
                            for region, districts in self.selected_site_map.items()
                                for district, sites in districts.items()
                                    for site in sites]


        for key in keys:
            data = self.get_data(key)
            for item in data:
                item = item.get('value', [])
                region = key[3]
                district = key[4]
                site_num = key[5]
                site_name = self.site_map.get(region, {}).get(district, {}).get(site_num)
                if item:
                    rows.append([
                        region,
                        district,
                        site_name if site_name else site_num,
                        usernames[key[1]],
                        item.get('totalBirths', 0),
                        item.get('totalFollowedUpByCallCenter', 0),
                        item.get('totalFollowedUpByDCO', 0),
                        self.get_hv_range(key),
                        self.get_hv_range(key, [8,14]),
                        self.get_hv_range(key, [21,-1])
                    ])

        return rows


class HVFollowUpStatusSummaryReport(HVFollowUpStatusReport):
    name = "Home Visit Follow Up Status Summary"
    slug = "hsph_hv_status_summary"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.SelectCaseStatusField',
              'hsph.fields.SiteField']

    def get_headers(self):
        return ["Region",
                "District",
                "Site",
                "Unique Patient ID",
                "Home Visit Status",
                "Name of mother",
                "Address where mother can be reachable in next 10 days",
                "Assigned By",
                "Allocated Data Collector",
                "Allocated Start Date",
                "Allocated End Date",
                "Visited Date",
                "Start Time",
                "End Time",
                "Duration (min)",
                "Within Allocated Period"]

    def get_parameters(self):
        super(HVFollowUpStatusSummaryReport, self).get_parameters()
        self.case_status = self.request.GET.get(SelectCaseStatusField.slug, None)

    def get_rows(self):
        rows = []
        data_not_found_text = 'unknown'
        no_data_text = '--'
        usernames = dict([(user.userID, util.format_datatables_data(user.username_in_report, user.raw_username)) for user in self.users ])

        if self.selected_site_map and self.case_status:
            keys = [["by_status_site", user.userID, dctl, self.case_status, region, district, site]
                        for user in self.users
                        for dctl in self.dctl_list
                        for region, districts in self.selected_site_map.items()
                            for district, sites in districts.items()
                                for site in sites]
        elif self.case_status and not self.selected_site_map:
            keys = [["by_status", user.userID, dctl, self.case_status]
                    for user in self.users
                    for dctl in self.dctl_list]
        elif self.selected_site_map and not self.case_status:
            keys = [["by_site", user.userID, dctl, region, district, site]
                        for user in self.users
                        for dctl in self.dctl_list
                        for region, districts in self.selected_site_map.items()
                            for district, sites in districts.items()
                                for site in sites]
        else:
            keys = [["all", user.userID, dctl]
                        for user in self.users
                        for dctl in self.dctl_list]

        for key in keys:
            data = self.get_data(key, reduce=False)
            for item in data:
                item = item.get('value', [])

                time_start = time_end = None
                total_time = allocated_period_default = no_data_text

                if item:
                    region = item.get('region', data_not_found_text)
                    district = item.get('district', data_not_found_text)
                    site_num = item.get('siteNum', data_not_found_text)
                    site_name = self.site_map.get(region, {}).get(district, {}).get(site_num)

                    start_date = dateutil.parser.parse(item.get('startDate'))
                    end_date = datetime.datetime.replace(dateutil.parser.parse(item.get('endDate')), tzinfo=pytz.utc)
                    visited_date = item.get('visitedDate')

                    if visited_date:
                        visited_date = dateutil.parser.parse(visited_date)
                        hv_form = XFormInstance.get(item.get('followupFormId'))
                        time_start = datetime.datetime.replace(hv_form.get_form['meta'].get('timeStart'), tzinfo=pytz.utc)
                        time_end = datetime.datetime.replace(hv_form.get_form['meta'].get('timeEnd'), tzinfo=pytz.utc)
                        total_time = time_end - time_start
                        total_time = "%d:%d" % (round(total_time.seconds/60),
                                                total_time.seconds-round(total_time.seconds/60))
                        allocated_period_default = "NO"

                    rows.append([
                        region,
                        district,
                        site_name if site_name else site_num,
                        item.get('patientId', data_not_found_text),
                        "CLOSED" if item.get('isClosed', False) else "OPEN",
                        item.get('nameMother', data_not_found_text),
                        item.get('address', data_not_found_text),
                        key[2],
                        usernames[key[1]],
                        start_date.strftime('%d-%b'),
                        end_date.strftime('%d-%b'),
                        visited_date.strftime('%d-%b') if visited_date else no_data_text,
                        time_start.strftime('%H:%M') if time_start else no_data_text,
                        time_end.strftime('%H:%M') if time_end else no_data_text,
                        total_time if total_time else no_data_text,
                        "YES" if time_end and time_end < end_date else allocated_period_default
                    ])
        return rows


class DCOProcessDataReport(HSPHFieldManagementReport, HSPHSiteDataMixin):
    name = "DCO Process Data Report"
    slug = "hsph_dco_process_data"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_headers(self):
        return ["Region",
                "District",
                "Site",
                "IHF/CHF",
                "Number of Births Observed",
                "Average Time Per Birth Record"]

    def get_parameters(self):
        self.generate_sitemap()
        if not self.selected_site_map:
            self.selected_site_map = self.site_map

    def get_rows(self):
        rows = []
        keys = [[region, district, site]
                        for region, districts in self.selected_site_map.items()
                            for district, sites in districts.items()
                                for site in sites]
        for key in keys:
            data = get_db().view("hsph/field_process_data",
                    reduce=True,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc]
                ).all()
            for item in data:
                item = item.get('value')

                if item:
                    region = key[0]
                    district = key[1]
                    site_num = key[2]
                    site_name = self.site_map.get(region, {}).get(district, {}).get(site_num)
                    reg_length = item.get('averageRegistrationLength', None)
                    avg_time = '--'
                    if reg_length:
                        reg_length = datetime.datetime.fromtimestamp(reg_length//1000)
                        avg_time = reg_length.strftime("%M:%S")
                    rows.append([
                        region,
                        district,
                        site_name if site_name else site_num,
                        '--',
                        item.get('totalBirths', 0),
                        avg_time
                    ])
        return rows