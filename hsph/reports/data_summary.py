from corehq.apps.reports import util
from corehq.apps.reports._global import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from hsph.fields import IHForCHFField
from hsph.reports import HSPHSiteDataMixin

class DataSummaryReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    """
        Base class for this section
    """
    pass

class PrimaryOutcomeReport(GenericTabularReport, DataSummaryReport, HSPHSiteDataMixin):
    name = "Primary Outcome Report"
    slug = "hsph_priamry_outcome"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']
    show_all_rows_option = True

    @property
    def headers(self):
        region = DataTablesColumn("Region")
        district = DataTablesColumn("District")
        site = DataTablesColumn("Site")
        num_births = DataTablesColumn("No. Birth Events Recorded")

        maternal_deaths = DataTablesColumn("Maternal Deaths", sort_type=DTSortType.NUMERIC)
        maternal_near_miss = DataTablesColumn("Maternal Near Miss", sort_type=DTSortType.NUMERIC)
        still_births = DataTablesColumn("Still Births", sort_type=DTSortType.NUMERIC)
        neonatal_mortality = DataTablesColumn("Neonatal Mortality", sort_type=DTSortType.NUMERIC)

        outcomes_on_discharge = DataTablesColumnGroup("Outcomes on Discharge",
            maternal_deaths,
            maternal_near_miss,
            still_births,
            neonatal_mortality)
        outcomes_on_discharge.css_span = 2

        outcomes_on_7days = DataTablesColumnGroup("Outcomes on 7 Days",
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


        primary_outcome = DataTablesColumn("Primary Outcome Yes")
        negative_outcome = DataTablesColumn("Primary Outcome No")
        lost = DataTablesColumn("Lost to Followup")

        return DataTablesHeader(region,
            district,
            site,
            num_births,
            outcomes_on_discharge,
            outcomes_on_7days,
            positive_outcomes,
            primary_outcome,
            negative_outcome,
            lost)

    @property
    def rows(self):
        rows = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
        keys = self.generate_keys(["site"])
        for key in keys:
            data = get_db().view('hsph/data_summary',
                reduce=True,
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc]
            ).all()
            for item in data:
                item = item.get('value', {})
                region, district, site = self.get_site_table_values(key[1:4])
                stat_keys = ['maternalDeaths', 'maternalNearMisses', 'stillBirthEvents', 'neonatalMortalityEvents']
                birth_events = item.get('totalBirthEventsOnRegistration', 0)
                row = [region,
                        district,
                        site,
                        birth_events]

                discharge_stats = item.get('atDischarge',{})
                on7days_stats = item.get('on7Days', {})
                discharge = []
                seven_days = []
                total = []
                for stat in stat_keys:
                    discharge.append(util.format_datatables_data('<span class="label">%d</span>' %
                                                                    discharge_stats.get(stat, 0),
                                                                    discharge_stats.get(stat, 0)) )
                    seven_days.append(util.format_datatables_data('<span class="label label-info">%d</span>' %
                                                                    on7days_stats.get(stat, 0),
                                                                    on7days_stats.get(stat, 0)))
                    total.append(util.format_datatables_data('<span class="label label-inverse">%d</span>' %
                                                                    item.get(stat, 0),
                                                                    item.get(stat, 0)))

                row.extend(discharge)
                row.extend(seven_days)
                row.extend(total)

                positive_outcomes = item.get('totalPositiveOutcomes', 0)
                lost_to_followup = item.get('lostToFollowUp', 0)
                negative_outcomes = max(birth_events - positive_outcomes - lost_to_followup, 0)

                row.extend([item.get('totalPositiveOutcomes', 0),
                            negative_outcomes,
                            item.get('lostToFollowUp', 0)])

                rows.append(row)
        return rows


class SecondaryOutcomeReport(DataSummaryReport):
    name = "Secondary Outcome Report"
    slug = "hsph_secondary_outcome"
    fields = ['corehq.apps.reports.fields.DatespanField']
    report_template_path = 'hsph/reports/comparative_data_summary.html'
    flush_layout = True

    @property
    def report_context(self):
        facilities = IHForCHFField.getIHFCHFFacilities()
        return dict(
            ihf_data=self._get_data(facilities['ihf']),
            chf_data=self._get_data(facilities['chf'])
        )

    def _get_data(self, facilities):
        num_births = 0
        birth_events = 0
        maternal_deaths = 0
        maternal_near_miss = 0
        still_births = 0
        neonatal_mortality = 0
        positive_outcomes = 0
        lost_to_followup = 0
        for facility in facilities:
            key = ["site_id", facility]
            data = get_db().view('hsph/data_summary',
                    reduce=True,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc]
            ).first()
            if not data:
                data = {}
            data = data.get('value', {})
            num_births += data.get('totalBirths', 0)
            birth_events += data.get('totalBirthEvents', 0)
            maternal_deaths += data.get('maternalDeaths', 0)
            maternal_near_miss += data.get('maternalNearMisses', 0)
            still_births += data.get('stillBirthEvents', 0)
            neonatal_mortality += data.get('neonatalMortalityEvents', 0)
            positive_outcomes += data.get('totalPositiveOutcomes', 0)
            lost_to_followup += data.get('lostToFollowUp', 0)
        negative_outcomes = max(birth_events - positive_outcomes - lost_to_followup, 0)
        return {
            "numBirths": num_births,
            "numBirthEvents": birth_events,
            "maternalDeaths": maternal_deaths,
            "maternalNearMiss": maternal_near_miss,
            "stillBirths": still_births,
            "neonatalMortality": neonatal_mortality,
            "positive": positive_outcomes,
            "negative": negative_outcomes,
            "lost": lost_to_followup
        }