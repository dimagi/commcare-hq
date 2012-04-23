import datetime
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from corehq.apps.reports import util
from hsph.fields import FacilityNameField

class DCOActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "DCO Activity Report"
    slug = "hsph_dco_activity"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField']

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
            key = [user.userID]
            num_facilities = 0
            num_fac_visits = 0
            num_fac_visits_lt2 = 0
            num_births = 0
            avg_time = "---"
            num_home_assigned = "---"
            num_home_completed = "---"
            num_home_21days = "---"

            data = get_db().view('hsph/dco_activity',
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
            rows.append([
                util.format_datatables_data(user.username_in_report, user.raw_username),
                "??",
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

class DCOFieldDataCollectionActivityReport(StandardTabularHQReport, StandardDateHQReport):
    name = "DCO Field Data Collection Activity Report"
    slug = "hsph_dco_field_data"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.FacilityNameField',
              'hsph.fields.NameOfDCOField',
              'hsph.fields.NameOfDCTLField']

    def get_headers(self):
        return ["Facility Name",
                "Name of DCO",
                "Name of DCTL",
                "No. of visits by DCO",
                "No. of births recorded",
                "No. of patients without contact details"]

    def get_rows(self):
        rows = []
        selected_fac = self.request.GET.get(FacilityNameField.slug, '')
        if selected_fac:
            facilities = [selected_fac]
        else:
            facilities = FacilityNameField.getFacilties()
        for user in self.users:
            for facility in facilities:
                key = [facility, user.userID]
                dctl_name = "??"
                data = get_db().view('hsph/dco_field_data_collection_activity',
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
                        dctl_name,
                        num_visits,
                        num_births,
                        num_births_no_contact
                    ])
                print data

        return rows