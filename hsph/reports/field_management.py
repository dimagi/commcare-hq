import datetime
import dateutil
import pytz
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from corehq.apps.reports import util
from hsph.fields import FacilityField, NameOfDCTLField, SiteField, SelectCaseStatusField
from hsph.reports import HSPHSiteDataMixin

class HSPHFieldManagementReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfFIDAField',
              'hsph.fields.NameOfDCTLField']

    _selected_dctl = None
    @property
    def selected_dctl(self):
        if self._selected_dctl is None:
            self._selected_dctl = self.request.GET.get(NameOfDCTLField.slug, '')
        return self._selected_dctl

    _dctl_fixture = None
    @property
    def dctl_fixture(self):
        if self._dctl_fixture is None:
            fixture = FixtureDataType.by_domain_tag(self.domain, "dctl").first()
            self._dctl_fixture = fixture.get_id if fixture else ''
        return self._dctl_fixture

    def user_to_dctl(self, user):
        dctl_name = "Unknown DCTL"
        dctl_id = None
        data_items = FixtureDataItem.by_user(user, domain=self.domain).all()
        for item in data_items:
            if item.data_type_id == self.dctl_fixture:
                dctl_id = item.fields.get('id')
                dctl_name = item.fields.get('name', dctl_name)
        return dctl_id, dctl_name

class DCOActivityReport(HSPHFieldManagementReport):
    name = "FIDA Activity Report"
    slug = "hsph_fida_activity"

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of FIDA"),
            DataTablesColumn("Name of DCTL"),
            DataTablesColumn("No. Facilities Covered"),
            DataTablesColumn("No. of Facility Visits"),
            DataTablesColumn("No. of Facility Visits with less than 2 visits/week"),
            DataTablesColumn("No. of Births Recorded"),
            DataTablesColumn("Average time per Birth Record (min)"),
            DataTablesColumn("No. of Births with no contact information provided"),
            DataTablesColumn("No. of Home Visits assigned"),
            DataTablesColumn("No. of Home Visits completed"),
            DataTablesColumn("No. of Home Visits open at 21 days"))

    @property
    def rows(self):
        rows = []
        for user in self.users:
            dctl_id, dctl_name = self.user_to_dctl(user)
            if self.selected_dctl and (self.selected_dctl != dctl_id):
                continue

            key = [user.get('user_id')]
            num_facilities = 0
            num_fac_visits = 0
            num_fac_visits_lt2 = 0
            num_births = 0
            avg_time = "---"
            births_without_contact = 0
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
                births_without_contact = data.get('totalBirthsWithoutContact', 0)
                if reg_length:
                    reg_length = datetime.datetime.fromtimestamp(reg_length//1000)
                    avg_time = reg_length.strftime("%M:%S")
                num_home_assigned = data.get('numHomeVisits', 0)
                num_home_completed = data.get('numHomeVisitsCompleted', 0)
                num_home_21days = data.get('numHomeVisitsOpenAt21', 0)
            rows.append([
                self.table_cell(user.get('raw_username'), user.get('username_in_report')),
                dctl_name,
                num_facilities,
                num_fac_visits,
                num_fac_visits_lt2,
                num_births,
                avg_time,
                births_without_contact,
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
              'hsph.fields.NameOfFIDAField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.FacilityField']

    _all_facilities = None
    @property
    def all_facilities(self):
        if self._all_facilities is None:
            self._all_facilities = FacilityField.getFacilities()
        return self._all_facilities

    _facility_name_map = None
    @property
    def facility_name_map(self):
        if self._facility_name_map is None:
            self._facility_name_map = dict([(facility.get('val'), facility.get('text'))
                                            for facility in self.all_facilities])
        return self._facility_name_map

    _facilities = None
    @property
    def facilities(self):
        if self._facilities is None:
            selected_fac = self.request.GET.get(FacilityField.slug, '')
            if selected_fac:
                self._facilities = [selected_fac]
            else:
                self._facilities = [facility.get("val") for facility in self.all_facilities]
        return self._facilities

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Facility Name"),
            DataTablesColumn("Name of DCO"),
            DataTablesColumn("Name of DCTL"),
            DataTablesColumn("No. of visits by DCO"),
            DataTablesColumn("No. of births recorded"),
            DataTablesColumn("No. of births without contact details"))

    @property
    def rows(self):
        rows = []
        for user in self.users:
            for facility in self.facilities:
                dctl_id, dctl_name = self.user_to_dctl(user)
                if self.selected_dctl and (self.selected_dctl != dctl_id):
                    continue

                key = [facility, user.get('user_id')]
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
                        self.facility_name_map[facility],
                        self.table_cell(user.get('raw_username'), user.get('username_in_report')),
                        dctl_name,
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
              'hsph.fields.NameOfFIDAField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.SiteField']

    def get_data(self, key, reduce=True):
        return get_db().view("hsph/field_follow_up_status",
            reduce=reduce,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc]
        ).all()

    def get_hv_range(self, original_key, dates=None):
        if not dates:
            dates = [0,8]
        key = [original_key[1], original_key[2], original_key[3], original_key[4]]
        now = self.datespan.enddate
        stop = now-datetime.timedelta(days=dates[0])
        stop = stop.strftime("%Y-%m-%d")
        last_day = dates[1]
        if last_day < 0:
            start = None
        else:
            start = now-datetime.timedelta(days=dates[1])
            start = start.strftime("%Y-%m-%d")
        data = get_db().view("hsph/cases_by_birth_date",
                                reduce=True,
                                startkey=key+[start],
                                endkey=key+[stop]
                            ).first()
        return data.get('value', 0) if data else 0

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("DCO Name"),
            DataTablesColumn("DCTL Name"),
            DataTablesColumn("No. Births Recorded"),
            DataTablesColumn("No. patients followed up by call center"),
            DataTablesColumn("No. patients followed up by DCO center"),
            DataTablesColumn("No. patients not yet open for follow up (<8 days)"),
            DataTablesColumn("No. patients open for DCC follow up (<14 days)"),
            DataTablesColumn("No. patients open for DCO follow up (>21 days)"))

    @property
    def rows(self):
        rows = []

        if not self.selected_site_map:
            self._selected_site_map = self.site_map

        for user in self.users:
            dctl_id, dctl_name = self.user_to_dctl(user)
            if self.selected_dctl and (self.selected_dctl != dctl_id):
                continue

            keys = self.generate_keys(prefix=["by_site", user.get('user_id')])
            for key in keys:
                data = self.get_data(key)
                for item in data:
                    item = item.get('value', [])
                    region, district, site = self.get_site_table_values(key[2:5])
                    if item:
                        rows.append([
                            region,
                            district,
                            site,
                            user.get('username_in_report'),
                            dctl_name,
                            item.get('totalBirths', 0),
                            item.get('totalFollowedUpByCallCenter', 0),
                            item.get('totalFollowedUpByDCO', 0),
                            self.get_hv_range(key),
                            self.get_hv_range(key, [8,14]),
                            self.get_hv_range(key, [21,-1])
                        ])

        return rows


class DCOProcessDataReport(HSPHFieldManagementReport, HSPHSiteDataMixin):
    name = "DCO Process Data Report"
    slug = "hsph_dco_process_data"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("IHF/CHF"),
            DataTablesColumn("Number of Births Observed"),
            DataTablesColumn("Average Time Per Birth Record"))

    @property
    def rows(self):
        rows = []

        if not self.selected_site_map:
            self._selected_site_map = self.site_map

        keys = self.generate_keys()

        for key in keys:
            data = get_db().view("hsph/field_process_data",
                    reduce=True,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc]
                ).all()
            for item in data:
                item = item.get('value')
                if item:
                    region, district, site = self.get_site_table_values(key)

                    reg_length = item.get('averageRegistrationLength', None)
                    avg_time = '--'
                    if reg_length:
                        reg_length = datetime.datetime.fromtimestamp(reg_length//1000)
                        avg_time = reg_length.strftime("%M:%S")
                    rows.append([
                        region,
                        district,
                        site,
                        '--',
                        item.get('totalBirths', 0),
                        avg_time
                    ])
        return rows
