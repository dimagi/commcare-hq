from corehq.apps.reports.standard import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup, DataTablesHeader, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.couch.database import get_db
from hsph.fields import IHForCHFField, SelectReferredInStatusField
from hsph.reports import HSPHSiteDataMixin

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
        region = DataTablesColumn("Region")
        district = DataTablesColumn("District")
        site = DataTablesColumn("Site")
        num_births = DataTablesColumn("No. Birth Events Recorded")
        num_referred_in_births = DataTablesColumn("No. Referred In Births")

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
            num_referred_in_births,
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

        if self.request_params.get(SelectReferredInStatusField.slug) == 'referred':
            keys = self.generate_keys(["site referred_in"])
        else:
            keys = self.generate_keys(["site"])

        for key in keys:
            data = get_db().view('hsph/data_summary',
                reduce=True,
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc]
            ).all()

            for item in data:

                item = item['value']
                region, district, site = self.get_site_table_values(key[1:4])
                birth_events = item['totalBirthRegistrationEvents']
                referred_in_birth_events = item['totalReferredInBirths']
                row = [region,
                        district,
                        site,
                        birth_events,
                        referred_in_birth_events]

                discharge_stats = item['atDischarge']
                on7days_stats = item['on7Days']
                discharge = []
                seven_days = []
                total = []

                stat_keys = ['maternalDeaths', 'maternalNearMisses', 'stillBirthEvents', 'neonatalMortalityEvents']
                for stat in stat_keys:
                    discharge.append(self.table_cell(discharge_stats[stat],
                                                     '<span class="label">%d</span>' % discharge_stats[stat]))
                    seven_days.append(self.table_cell(on7days_stats[stat],
                                                      '<span class="label label-info">%d</span>' % on7days_stats[stat]))
                    total.append(self.table_cell(item[stat],
                                                 '<span class="label label-inverse">%d</span>' % item[stat]))

                row.extend(discharge)
                row.extend(seven_days)
                row.extend(total)

                negative_outcomes = item['totalBirthRegistrationEvents'] - \
                                    item['positiveOutcomeEvents'] - \
                                    item['lostToFollowUp']

                row.extend([item['positiveOutcomeEvents'],
                            negative_outcomes,
                            item['lostToFollowUp']])

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
        facilities = IHForCHFField.get_selected_facilities(site_map)

        return dict(
            ihf_data=self._get_data(facilities['ihf']),
            chf_data=self._get_data(facilities['chf'])
        )

    def _get_data(self, facilities):
        fields = [
            'totalBirthRegistrationEvents',
            'totalBirths',
            'totalBirthEvents',
            'followedUp',
            'lostToFollowUp',
            'maternalDeaths',
            'maternalNearMisses',
            'stillBirthEvents',
            'neonatalMortalityEvents',
            'positiveOutcomeEvents',
            'combinedMortalityOutcomes'
        ]

        data = dict([(f, 0) for f in fields])
        db = get_db()

        for facility in facilities:
            key = ["site_id", facility]

            result = db.view('hsph/data_summary',
                reduce=True,
                startkey=key + [self.datespan.startdate_param_utc],
                endkey=key + [self.datespan.enddate_param_utc]
            ).first()

            if not result:
                continue

            result = result['value']

            for field in data:
                data[field] += result[field]

        data['negativeOutcomeEvents'] = data['totalBirthRegistrationEvents'] - \
                                        data['positiveOutcomeEvents'] - \
                                        data['lostToFollowUp']
        return data


class FADAObservationsReport(DataSummaryReport, HSPHSiteDataMixin):
    name = "FADA Observations"
    slug = "fada_observations"

    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfFADAField']

    report_template_path = 'hsph/reports/fada_observations.html'
    flush_layout = True

    @property
    def report_context(self):
        keys = [
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
            "med_antiobiotics_baby"
        ]

        values = dict((k, 0) for k in keys)

        db = get_db()

        for user_id in self.user_ids:
            results = db.view("hsph/fada_observations",
                reduce=True,
                group_level=3,
                startkey=[user_id, self.datespan.startdate_param_utc],
                endkey=[user_id, self.datespan.enddate_param_utc],
                wrapper=lambda r: r['value']
            )

            for result in results:
                for k, v in result.items():
                    values[k] += v

        unique_sbrs = values['unique_sbrs'] = values['total_forms']
        for k, v in values.items():
            if unique_sbrs:
                values[k + '_pct'] = round(float(v) * 100 / unique_sbrs, 1)
            else:
                values[k + '_pct'] = '---'

        return values


