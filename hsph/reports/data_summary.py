from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader, DTSortType
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from hsph.reports.common import HSPHSiteDataMixin

class ProgramDataSummaryReport(StandardTabularHQReport, StandardDateHQReport, HSPHSiteDataMixin):
    name = "Program Data Summary"
    slug = "hsph_program_summary"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    def get_parameters(self):
        self.generate_sitemap()
        if not self.selected_site_map:
            self.selected_site_map = self.site_map

    def get_headers(self):

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


        primary_outcome = DataTablesColumn("Primary Outcome Positive")
        negative_outcome = DataTablesColumn("Total Negative Outcomes")
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

    def get_rows(self):
        rows = []
        keys = self.generate_keys(["site"])
        print keys
        for key in keys:
            data = get_db().view('hsph/data_summary',
                reduce=True,
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc]
            ).all()
            for item in data:
                item = item.get('value', {})
                region, district, site_num, site_name = self.get_site_table_values(key[1:4])
                stat_keys = ['maternalDeaths', 'maternalNearMisses', 'stillBirthEvents', 'neonatalMortalityEvents']
                birth_events = item.get('totalBirthEvents', 0)
                row = [region,
                        district,
                        site_name if site_name else site_num,
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


class ComparativeDataSummaryReport(StandardDateHQReport):
    name = "Comparative Data Summary Report"
    slug = "hsph_comparative_data_summary"
    fields = ['corehq.apps.reports.fields.DatespanField']
    template_name = 'hsph/reports/comparative_data_summary.html'

    def calc(self):
        self.context['ihf_data'] = self.get_data_for_type()
        self.context['chf_data'] = self.get_data_for_type("CHF")


    def get_data_for_type(self, ihf_or_chf="IHF"):
        data = get_db().view('hsph/data_summary',
                reduce=True,
                startkey=["type", ihf_or_chf, self.datespan.startdate_param_utc],
                endkey=["type", ihf_or_chf, self.datespan.enddate_param_utc]
        ).first()
        if not data:
            data = {}
        data = data.get('value', {})
        birth_events = data.get('totalBirthEvents', 0)
        positive_outcomes = data.get('totalPositiveOutcomes', 0)
        lost_to_followup = data.get('lostToFollowUp', 0)
        negative_outcomes = max(birth_events - positive_outcomes - lost_to_followup, 0)
        return {
            "numBirths": data.get('totalBirths', 0),
            "numBirthEvents": birth_events,
            "maternalDeaths": data.get('maternalDeaths', 0),
            "maternalNearMiss": data.get('maternalNearMisses', 0),
            "stillBirths": data.get('stillBirthEvents', 0),
            "neonatalMortality": data.get('neonatalMortalityEvents', 0),
            "positive": positive_outcomes,
            "negative": negative_outcomes,
            "lost": lost_to_followup
        }