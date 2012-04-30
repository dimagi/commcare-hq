import datetime
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from corehq.apps.reports import util
from hsph.fields import FacilityField, NameOfDCTLField

class DCOActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "DCO Activity Report"
    slug = "hsph_dco_activity"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField']
    dctl_list = NameOfDCTLField.dctl_list

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

class FieldDataCollectionActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "Field Data Collection Activity Report"
    slug = "hsph_field_data"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.FacilityField']
    dctl_list = NameOfDCTLField.dctl_list

    def get_headers(self):
        return ["Facility Name",
                "Name of DCO",
                "Name of DCTL",
                "No. of visits by DCO",
                "No. of births recorded",
                "No. of births without contact details"]

    def get_parameters(self):
        selected_fac = self.request.GET.get(FacilityField.slug, '')
        if selected_fac:
            self.facilities = [selected_fac]
        else:
            self.facilities = FacilityField.getFacilties()

        selected_dctl = self.request.GET.get(NameOfDCTLField.slug, '')
        if selected_dctl:
            self.dctl_list = [selected_dctl]

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
                    print data

        return rows

class HVFollowUpStatusSummary(StandardTabularHQReport, StandardDateHQReport):
    name = "Home Visit Follow Up Status Summary"
    slug = "hsph_hv_status_summary"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField',
              'hsph.fields.SiteField']

    def get_headers(self):
        return ["Region",
                "District",
                "Site ID",
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

    def get_rows(self):
        rows = []
        return rows