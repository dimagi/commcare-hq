import datetime
from corehq.apps.groups.models import Group
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.basic import BasicTabularReport, Column
from corehq.apps.reports.standard import (DatespanMixin,
    ProjectReportParametersMixin, CustomProjectReport)
from corehq.apps.reports.standard.inspect import CaseDisplay, CaseListReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from hsph.reports import HSPHSiteDataMixin
from hsph.fields import NameOfCATIField, AllocatedToFilter
from corehq.apps.reports.fields import FilterUsersField, DatespanField
from couchdbkit_aggregate.fn import mean, unique_count
from casexml.apps.case import const
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.couch.database import get_db

def short_date_format(date):
    return date.strftime('%d-%b')


def username(key, report):
    return report.usernames[key[0]]


def datestring_minus_days(datestring, days):
    date = datetime.datetime.strptime(datestring[:10], '%Y-%m-%d')
    return (date - datetime.timedelta(days=days)).isoformat()


def date_minus_11_days(couchkey):
    return couchkey + [datestring_minus_days(couchkey[0], 11)]


def date_minus_14_days(couchkey):
    return couchkey + [datestring_minus_days(couchkey[0], 14)]


class CATIPerformanceReport(CustomProjectReport, ProjectReportParametersMixin,
                            DatespanMixin, BasicTabularReport):
    name = "CATI Performance Report"
    slug = "cati_performance"
    field_classes = (FilterUsersField, DatespanField, NameOfCATIField)
            
    filter_group_name = "CATI"
    
    couch_view = "hsph/cati_performance_report"
    
    default_column_order = (
        'catiName',
        'followedUp',
        'noFollowUpAfter4Days',
        'transferredToManager',
        'transferredToField',
        'notClosedOrTransferredAfter13Days',
        'workingDaysUniqueCount',
        'followUpTime',
        'followUpTimeMean'
    )

    catiName = Column(
        "Name of CATI", calculate_fn=username)

    followedUp = Column(
        "No. of Births Followed Up", key='followedUp')

    noFollowUpAfter4Days = Column(
        "No. of Cases with No Follow Up for 4 Days",
        key='noFollowUpAfter4Days',
        endkey_fn=date_minus_11_days)

    transferredToManager = Column(
        "Transferred to Call Center Manager", key='transferredToManager')

    transferredToField = Column(
        "Transferred to Field", key='transferredToField')

    notClosedOrTransferredAfter13Days = Column(
        "CATI Timed Out", key='notClosedOrTransferredAfter13Days',
        endkey_fn=date_minus_14_days)

    workingDaysUniqueCount = Column(
        "No. of Working Days", key='workingDays', reduce_fn=unique_count)

    followUpTime = Column(
        "Total Follow Up Time", key='followUpTime')

    followUpTimeMean = Column(
        "Average Follow Up Time", key='followUpTime', reduce_fn=mean)

    @property
    def start_and_end_keys(self):
        return ([self.datespan.startdate_param_utc],
                [self.datespan.enddate_param_utc])

    @property
    def keys(self):
        for user in self.users:
            yield [user['user_id']]


class HSPHCaseDisplay(CaseDisplay):
    
    @property
    def region(self):
        try:
            return self.report.get_region_name(self.case.region_id)
        except AttributeError:
            return ""

    @property
    def district(self):
        try:
            return self.report.get_district_name(
                self.case.region_id, self.case.district_id)
        except AttributeError:
            return ""

    @property
    def site(self):
        try:
            return self.report.get_site_name(
                self.case.region_id, self.case.district_id,
                self.case.site_number)
        except AttributeError:
            return ""

    @property
    def patient_id(self):
        try:
            return self.case.patient_id
        except AttributeError:
            return ""

    @property
    def status(self):
        return "Closed" if self.case.closed else "Open"

    @property
    def mother_name(self):
        return getattr(self.case, 'name_mother', '')

    @property
    def filter_date(self):
        return str(getattr(self.case, 'filter_date', ''))

    @property
    def address(self):
        return getattr(self.case, 'house_address', '')

    @property
    @memoized
    def allocated_to(self):
        if self.status == "Closed":
            close_action = [a for a in self.case.actions if a.action_type ==
                const.CASE_ACTION_CLOSE][0]

            CATI_FOLLOW_UP_FORMS = (
                "http://openrosa.org/formdesigner/A5B08D8F-139D-46C6-9FDF-B1AD176EAE1F",
            )
            if close_action.xform.xmlns in CATI_FOLLOW_UP_FORMS:
                return 'CATI'
            else:
                return 'Field'

        else:
            follow_up_type = getattr(self.case, 'follow_up_type', '')
            house_number = getattr(self.case, 'phone_house_number', '')
            husband_number = getattr(self.case, 'phone_husband_number', '')
            mother_number = getattr(self.case, 'phone_mother_number', '')
            asha_number = getattr(self.case, 'phone_asha_number', '')

            if follow_up_type != 'field_follow_up' and (house_number or
                   husband_number or mother_number or asha_number):
                return 'CATI'
            else:
                return 'Field'

    @property
    def allocated_start(self):
        try:
            delta = datetime.timedelta(days=8 if self.allocated_to == 'CATI' else 13)
            return short_date_format(self.case.filter_date + delta)
        except AttributeError:
            return ""

    @property
    def allocated_end(self):
        try:
            delta = datetime.timedelta(days=13 if self.allocated_to == 'CATI' else 23)
            return short_date_format(self.case.filter_date + delta)
        except AttributeError:
            return ""

    @property
    def outside_allocated_period(self):
        if not (hasattr(self.case, 'filter_date') and
                isinstance(self.case.filter_date, datetime.date)):
            return ""

        if self.case.closed_on:
            compare_date = self.case.closed_on.date()
        else:
            compare_date = datetime.date.today()

        return 'Yes' if (compare_date - self.case.filter_date).days > 23 else 'No'


class CaseReport(CaseListReport, CustomProjectReport, HSPHSiteDataMixin,
                 DatespanMixin):
    name = 'Case Report'
    slug = 'case_report'
    
    fields = (
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.DatespanField',
        'hsph.fields.SiteField',
        #'hsph.fields.AllocatedToFilter',
        #'hsph.fields.DCTLAndFIDAFilter',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    )

    default_case_type = 'birth'

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("Patient ID"),
            DataTablesColumn("Status"),
            DataTablesColumn("Mother Name"),
            DataTablesColumn("Date of Delivery or Admission"),
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
        #allocated_to = self.request_params.get(AllocatedToFilter.slug, '')
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

        #if allocated_to:
            #filters.append({'term': {'allocated_to': allocated_to}})

        if site_num:
            filters.append({'term': {'site_number': site_num.lower()}})
        if district_id:
            filters.append({'term': {'district_id': district_id.lower()}})
        if region_id:
            filters.append({'term': {'region_id': region_id.lower()}})
        
        return {'and': filters} if filters else {}

        #def allocated_to(self):
            #if self.status == "Closed":
                #close_action = [a for a in self.case.actions if a.action_type ==
                    #const.CASE_ACTION_CLOSE][0]

                #CATI_FOLLOW_UP_FORMS = (
                    #"http://openrosa.org/formdesigner/A5B08D8F-139D-46C6-9FDF-B1AD176EAE1F",
                #)
                #if close_action.xform.xmlns in CATI_FOLLOW_UP_FORMS:
                    #return 'CATI'
                #else:
                    #return 'Field'

            #else:
                #follow_up_type = getattr(self.case, 'follow_up_type', '')
                #house_number = getattr(self.case, 'phone_house_number', '')
                #husband_number = getattr(self.case, 'phone_husband_number', '')
                #mother_number = getattr(self.case, 'phone_mother_number', '')
                #asha_number = getattr(self.case, 'phone_asha_number', '')

                #if follow_up_type != 'field_follow_up' and (house_number or
                       #husband_number or mother_number or asha_number):
                    #return 'CATI'
                #else:
                    #return 'Field'


    @property
    def shared_pagination_GET_params(self):
        params = super(CaseReport, self).shared_pagination_GET_params

        slugs = [
            AllocatedToFilter.slug,
            'hsph_region',
            'hsph_district',
            'hsph_site',
            'dctl_fida_dctl',
            'dctl_fida_fida',
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
    def user_ids(self):
        fida_user_id = self.request_params.get('dctl_fida_fida', None)
        dctl_group_id = self.request_params.get('dctl_fida_dctl', None)

        if fida_user_id:
            return [fida_user_id]
        elif dctl_group_id:
            return Group.get(dctl_group_id).get_user_ids()
        else:
            return super(CaseReport, self).user_ids

    @property
    def rows(self):
        case_displays = (HSPHCaseDisplay(self, self.get_case(case))
                         for case in self.case_results['rows'])

        for disp in case_displays:
            yield [
                disp.region,
                disp.district,
                disp.site,
                disp.patient_id,
                disp.status,
                disp.case_link,
                disp.filter_date,
                disp.address,
                disp.allocated_to,
                disp.allocated_start,
                disp.allocated_end,
                disp.outside_allocated_period
            ]


class CallCenterFollowUpSummaryReport(GenericTabularReport,
        CustomProjectReport, ProjectReportParametersMixin, DatespanMixin,
        HSPHSiteDataMixin):
    name = "Call Center Follow Up Summary"
    slug = "hsph_dcc_followup_summary"

    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("Total Number of Birth events with contact details"),
            DataTablesColumn("Total number of births followed up"),
            DataTablesColumn("Number of cases followed up at day 8th"),
            DataTablesColumn("Number of cases followed up between day 9th to 13th"),
            DataTablesColumn("Number of cases with contact details open at day 14th"),
            DataTablesColumn("Number of cases with contact details transferred to Field management for home Visits"),
            DataTablesColumn("Number of cases where no out comes could be recorded"))

    @property
    def rows(self):
        db = get_db()
        rows = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
        keys = self.generate_keys()
        for key in keys:
            data = db.view("hsph/dcc_followup_summary",
                reduce=True,
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc]
            ).all()
            for item in data:
                item = item.get('value')
                if item:
                    region, district, site = self.get_site_table_values(key)

                    now = self.datespan.enddate
                    day14 = now-datetime.timedelta(days=14)
                    day14 = day14.strftime("%Y-%m-%d")
                    day14_data = db.view("hsph/cases_by_birth_date",
                                reduce=True,
                                startkey=key,
                                endkey=key+[day14]
                            ).first()
                    still_open_at_day14 = day14_data.get('value', 0) if day14_data else 0

                    rows.append([
                        region,
                        district,
                        site,
                        item.get('totalBirthsWithContact', 0),
                        item.get('totalBirths', 0),
                        item.get('numCasesFollowedUpByDay8', 0),
                        item.get('numCasesFollowedUpBetweenDays9and13', 0),
                        still_open_at_day14,
                        item.get('numCasesWithContactTransferredToField', 0),
                        item.get('numCasesWithNoOutcomes', 0)
                    ])
        return rows

