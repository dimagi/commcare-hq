from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.couch.database import get_db
from hsph.fields import IHForCHFField, SelectReferredInStatusField
from hsph.reports import HSPHSiteDataMixin
    
from collections import defaultdict
from django.utils.translation import ugettext as _
from datetime import date, timedelta, time

class DataSummaryReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    """
        Base class for this section
    """
    pass

class PrimaryOutcomeReport(GenericTabularReport, DataSummaryReport, HSPHSiteDataMixin):
    name = "Primary Outcome Report"
    slug = "hsph_primary_outcome"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SelectReferredInStatusField',
              'hsph.fields.SiteField']

    show_all_rows_option = True

    @property
    def headers(self):

        maternal_deaths = DataTablesColumn("Maternal Deaths", sort_type=DTSortType.NUMERIC)
        maternal_near_miss = DataTablesColumn("Maternal Near Miss", sort_type=DTSortType.NUMERIC)
        still_births = DataTablesColumn("Still Births", sort_type=DTSortType.NUMERIC)
        neonatal_mortality = DataTablesColumn("Neonatal Mortality", sort_type=DTSortType.NUMERIC)

        outcomes_on_discharge = DataTablesColumnGroup("Outcomes on Discharge",
            maternal_deaths,
            still_births,
            neonatal_mortality)
        outcomes_on_discharge.css_span = 2

        outcomes_on_7days = DataTablesColumnGroup("Outcomes at 7 Days",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        outcomes_on_7days.css_span = 2

        positive_outcomes = DataTablesColumnGroup("Total Positive Outcomes",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        positive_outcomes.css_span = 2

        return DataTablesHeader(
            DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("Birth Events"),
            DataTablesColumn("Referred In Births"),
            outcomes_on_discharge,
            outcomes_on_7days,
            positive_outcomes,
            DataTablesColumn("Primary Outcome Yes"),
            DataTablesColumn("Primary Outcome No"),
            DataTablesColumn("Lost to Follow Up")
        )

    @property
    def rows(self):
        rows = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
        
        site_keys = self.generate_keys()

        referred = self.request_params.get(SelectReferredInStatusField.slug)
        prefix = ['referred_in'] if referred else []
        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]

        fields = [
            'birthEvents',
            'referredInBirths',
            'maternalDeaths',
            'stillBirths',
            'neonatalMortality',
            'maternalDeaths7Days',
            'maternalNearMisses7Days',
            'stillBirths7Days',
            'neonatalMortalityEvents7Days',
            'totalMaternalDeaths',
            'totalMaternalNearMisses',
            'totalStillBirths',
            'totalNeonatalMortalityEvents',
            'positiveOutcome',
            'negativeOutcome',
            'lostToFollowUp'
        ]

        for key in site_keys:
            wtf = key
            wtf[2] = str(wtf[2])

            data = get_db().view('hsph/data_summary', 
                startkey=[self.domain] + prefix + ['region'] + wtf + [startdate], 
                endkey=[self.domain] + prefix + ['region'] + wtf + [enddate],
                reduce=True,
                wrapper=lambda r: r['value'])

            for item in data:
                row = list(self.get_site_table_values(key))
                row.extend(item.get(f, 0) for f in fields)

                rows.append(row)
        return rows


class SecondaryOutcomeReport(DataSummaryReport, HSPHSiteDataMixin):
    name = "Secondary Outcome Report"
    slug = "hsph_secondary_outcome"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']
    report_template_path = 'hsph/reports/comparative_data_summary.html'
    flush_layout = True

    @property
    def report_context(self):
        site_map = self.selected_site_map or self.site_map
        facilities = IHForCHFField.get_selected_facilities(
                site_map, domain=self.domain)

        return dict(
            ihf_data=self._get_data(facilities['ihf']),
            chf_data=self._get_data(facilities['chf'])
        )

    def _get_data(self, site_ids):
        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]

        def per(field, denom_field, denom_multiplier):
            def calculate(data):
                denom = data.get(denom_field, 0)
                if denom:
                    return denom_multiplier * data.get(field, 0) / float(denom)
                else:
                    return '---'
            return calculate

        extra_fields = {
            'maternalDeathsPer100000LiveBirths': per('totalMaternalDeaths', 'liveBirthsSum', 100000),
            'maternalNearMissesPer1000LiveBirths': per('totalMaternalNearMisses', 'liveBirthsSum', 1000),
            'referredInBirthsPer1000LiveBirths': per('referredInBirths', 'liveBirthsSum', 1000),
            'cSectionsPer1000LiveBirths': per('cSections', 'liveBirthsSum', 1000),
            'stillBirthsPer1000LiveBirths': per('totalStillBirthsSum', 'liveBirthsSum', 1000),
            'neonatalMortalityEventsPer1000LiveBirths': per('neonatalMortalityEvents7DaysSum', 'liveBirthsSum', 1000),
            'referredOutPer1000LiveBirths': per('referredOut', 'liveBirthsSum', 1000),
        }

        data = defaultdict(int)
        db = get_db()

        for site_id in site_ids:
            result = db.view('hsph/data_summary',
                reduce=True,
                startkey=[self.domain, "site", site_id, startdate],
                endkey=[self.domain, "site", site_id, enddate],
                wrapper=lambda r: r['value']
            ).first()

            if result:
                for field, value in result.items():
                    data[field] += value

        data.update(FADAObservationsReport.get_values(
                self.domain, (startdate, enddate), site_ids=site_ids))

        for k, calc in extra_fields.items():
            data[k] = calc(data)

        return data


class FADAObservationsReport(DataSummaryReport, HSPHSiteDataMixin):
    name = "FADA Observations"
    slug = "fada_observations"

    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfFADAField',
              'hsph.fields.SiteField']

    report_template_path = 'hsph/reports/fada_observations.html'
    flush_layout = True

    @classmethod
    def get_values(cls, domain, daterange, site_ids=None, user_ids=None):
        """
        Gets reduced results per unique process_sbr_no for each key and sums
        them together, adding percentage occurences out of total_forms for all
        indicators.

        """

        site_ids = site_ids or []
        user_ids = user_ids or []
        startdate, enddate = daterange
        keys = []
        keys.extend([(["site", site_id, startdate],
                      ["site", site_id, enddate])
                     for site_id in site_ids])
        keys.extend([(["user", user_id, startdate],
                      ["user", user_id, enddate])
                     for user_id in user_ids])

        data_keys = [
            "total_forms",
            "pp1_observed",
            "pp1_maternal_temp",
            "pp1_maternal_bp",
            "pp1_partograph",
            "pp1_scc_used_pp1",
            "pp1_pp_1_birth_companion_present",
            "pp2_observed",
            "pp2_oxycotin_started",
            "pp2_soap",
            "pp2_water",
            "pp2_gloves_used",
            "pp2_scc_used_pp2",
            "pp2_pp3_birth_companion_present",
            "pp3_observed",
            "pp3_oxycotin",
            "pp3_baby_apneic",
            "pp3_baby_intervention",
            "pp3_pp_3_birth_companion_present",
            "pp4_observed",
            "pp4_baby_wt",
            "pp4_baby_temp",
            "pp4_breastfeeding",
            "pp4_scc_used_pp4",
            "pp4_pp_4_birth_companion_present",
            "medication_observed",
            "med_oxycotin_admin",
            "med_ab_mother",
            "med_mgsulp",
            "med_ab_baby",
            "med_art_mother",
            "med_art_baby",

            "pp2_soap_and_water"
        ]

        values = dict((k, 0) for k in data_keys)
        db = get_db()

        all_results = []

        for startkey, endkey in keys:
            results = db.view("hsph/fada_observations",
                reduce=True,
                group_level=5,
                startkey=[domain] + startkey,
                endkey=[domain] + endkey)

            all_results.extend(results)

        # "The same sbr no forms are definitely not going to come from
        # different users." -- Sheel
        seen_process_sbr_nos = set()
        for result in all_results:
            value = result['value']
            process_sbr_no = result['key'][4]

            if process_sbr_no not in seen_process_sbr_nos:
                if value['site_id'] in site_ids and value['user_id'] in user_ids:
                    for k, v in value.items():
                        if k not in ('site_id', 'user_id'):
                            values[k] += v
                seen_process_sbr_nos.add(process_sbr_no)

        for k, v in values.items():
            pp = ('medication' if k[:3] == 'med' else k[:3]) + "_observed"
            if pp in values:
                if values[pp]:
                    values[k + '_pct'] = round(float(v) * 100 / values[pp], 1)
                else:
                    values[k + '_pct'] = '---'

        # used by secondary outcome report
        if values['pp3_baby_apneic']:
            values['pp3_apneic_intervention_pct'] = round(
                100 * float(values['pp3_baby_intervention']) / values['pp3_baby_apneic'], 1)
        else:
            values['pp3_apneic_intervention_pct'] = '---'
        
        values['unique_sbrs'] = values['total_forms']

        return values

    @property
    def report_context(self):
        site_map = self.selected_site_map or self.site_map
        facilities = IHForCHFField.get_selected_facilities(site_map, self.domain)

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]

        user_ids = self.user_ids

       
        return {
            'ihf': self.get_values(
                    self.domain, (startdate, enddate),
                    site_ids=facilities['ihf'],
                    user_ids=user_ids),
            'chf': self.get_values(
                    self.domain, (startdate, enddate),
                    site_ids=facilities['chf'],
                    user_ids=user_ids)
        }

class FacilityWiseFollowUpRepoert(GenericTabularReport, DataSummaryReport, 
                                                        HSPHSiteDataMixin):
    name = "Facility Wise Follow Up Report"
    slug = "hsph_facility_wise_follow_up"
    fields = ['corehq.apps.reports.fields.DatespanField',
               'corehq.apps.reports.fields.GroupField',
              'hsph.fields.NameOfFIDAField']
              
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

        site_keys = get_db().view('hsph/facility_wise_follow_up',
                    reduce=True,
                    group=True, group_level=5)

        rpt_keys = []
        key_start = []

        if self.individual:
            for entry in site_keys:
                if entry['key'][-1] == self.individual:
                    rpt_keys.append(entry)
        elif self.user_ids:
            for entry in site_keys:
                if entry['key'][-1] in self.user_ids:
                    rpt_keys.append(entry)
        else:
            rpt_keys = site_keys

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
        today_str = today.strftime('%Y-%m-%d')
        for item in  rpt_keys:
            key_start = item['key']
            region_id, district_id, site_id, site_number, user_id = item['key']
            region_name = self.get_region_name(region_id)
            district_name = self.get_district_name(region_id, district_id)
            
            if site_number.isdigit() and int(site_number) > 9:
                site_name = self.get_site_name(region_id, district_id, 
                int(site_number))
            else:
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
    