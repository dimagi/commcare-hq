import datetime
from django.utils.safestring import mark_safe
import logging
import numpy
from corehq.apps.indicators.models import DynamicIndicatorDefinition, CombinedCouchViewIndicatorDefinition
from mvp.models import MVP
from mvp.reports import MVPIndicatorReport

class HealthCoordinatorReport(MVPIndicatorReport):
    """
        MVP Custom Report: MVIS Health Coordinator
    """
    slug = "health_coordinator"
    name = "MVIS Health Coordinator Report"
    report_template_path = "mvp/reports/health_coordinator.html"
    hide_filters = True
    fields = []

    @property
    def report_context(self):
        report_matrix = list()
        month_headers = None
        for category_group in self.indicator_slugs:
            category_indicators = list()
            total_rowspan = 0
            for slug in category_group['indicator_slugs']:
                indicator = DynamicIndicatorDefinition.get_current(MVP.NAMESPACE, self.domain, slug, wrap_correctly=True)
                if indicator:
                    retrospective = indicator.get_monthly_retrospective()
                    if not month_headers:
                        month_headers = self.get_month_headers(retrospective)

                    if isinstance(indicator, CombinedCouchViewIndicatorDefinition):
                        table = self.get_indicator_table(retrospective)
                        indicator_rowspan = 3
                    else:
                        table = self.get_indicator_row(retrospective)
                        indicator_rowspan = 1
                    total_rowspan += indicator_rowspan + 1
                    category_indicators.append(dict(
                        title=indicator.description,
                        values=retrospective,
                        table=table,
                        rowspan=indicator_rowspan
                    ))
                else:
                    logging.info("Could not grab indicator %s in domain %s" % (slug, self.domain))
            report_matrix.append(dict(
                category_title=category_group['category_title'],
                rowspan=total_rowspan,
                indicators=category_indicators,
            ))
        return dict(
            months=month_headers,
            report=report_matrix,
        )

    @property
    def indicator_slugs(self):
        return  [
            dict(
                category_title="Child Health",
                indicator_slugs=[
                    "under5_fever_rdt_proportion",
                    "under5_fever_rdt_positive_proportion",
                    "under5_fever_rdt_positive_medicated_proportion",
                    "under5_fever_rdt_negative_medicated_proportion",
                    "under5_fever_rdt_not_received_proportion",
                    "under5_diarrhea_ors_proportion",
                    "under5_diarrhea_zinc_proportion",
                    "under5_complicated_fever_facility_followup_proportion",
                    "under5_complicated_fever_referred_proportion",
                    "under1_check_ups_proportion",
                ]
            ),
            dict(
                category_title="Child Nutrition",
                indicator_slugs=[
                    "muac_wasting_proportion",
                    "muac_routine_proportion",
                    "under6month_exclusive_breastfeeding_proportion",
                    "low_birth_weight_proportion",
                ]
            ),
            dict(
                category_title="CHW Visits",
                indicator_slugs=[
                    "households_routine_visit_past90days",
                    "households_routine_visit_past30days",
                    "under5_routine_visit_past30days",
                    "pregnant_routine_visit_past30days",
                    "neonate_routine_visit_past7days",
                    "urgent_referrals_proportion",
                    "newborn_7day_visit_proportion",
                ]
            ),
            dict(
                category_title="CHW Mgmt",
                indicator_slugs=[
                    "median_days_referral_followup",
                ]
            ),
            dict(
                category_title="Maternal",
                indicator_slugs=[
                    "family_planning_proportion",
                    "anc4_proportion",
                    "facility_births_proportion",
                    "pregnant_routine_checkup_proportion",
                ]
            ),
            dict(
                category_title="Births",
                indicator_slugs=[
                    "num_births_registered",
                ]
            ),
            dict(
                category_title="Deaths",
                indicator_slugs=[
                    "neonatal_deaths",
                    "infant_deaths",
                    "under5_deaths",
                    "maternal_deaths",
                    "over5_deaths",
                ]
            )
        ]

    def get_month_headers(self, retrospective):
        headers = list()
        month_fmt = "%b %Y"
        num_months = len(retrospective)
        for i, result in enumerate(retrospective):
            month = result.get('date')
            month_text = month.strftime(month_fmt) if isinstance(month, datetime.datetime) else "Unknown"
            month_desc = "(-%d)" % (num_months-(i+1)) if (num_months-i) > 1 else "(Current)"
            headers.append(mark_safe("%s<br />%s" % (month_text, month_desc)))
        return headers

    def get_indicator_table(self, retrospective):
        n_row = [i.get('numerator', 0) for i in retrospective]
        d_row = [i.get('denominator', 0) for i in retrospective]
        r_row = [i.get('ratio') for i in retrospective]

        n_stats = []
        d_stats = []
        r_stats = []
        for i in range(len(retrospective)):
            if r_row[i] is not None:
                n_stats.append(n_row[i])
                d_stats.append(d_row[i])
                r_stats.append(r_row[i])

        n_row.extend(self._get_statistics(n_stats))
        d_row.extend(self._get_statistics(d_stats))
        r_row.extend(self._get_statistics(r_stats))

        return dict(
            numerators=self._format_row(n_row),
            denominators=self._format_row(d_row),
            percentages=self._format_row(r_row, True)
        )

    def _format_row(self, row, as_percent=False):
        formatted = list()
        num_cols = len(row)
        for i, val in enumerate(row):
            if val is not None and not numpy.isnan(val):
                text = "%.f%%" % (val*100) if as_percent else "%d" % int(val)
            else:
                text = "--"

            if i == num_cols-4:
                css = "current_month"
            elif i > num_cols-4:
                css = "summary"
            else:
                css = ""

            formatted.append(dict(
                raw_value=val,
                text=text,
                css=css
            ))
        return formatted

    def _get_statistics(self, nonzero_row):
        return [numpy.average(nonzero_row), numpy.median(nonzero_row), numpy.std(nonzero_row)]

    def get_indicator_row(self, retrospective):
        row = [i.get('value', 0) for i in retrospective]
        nonzero_row = [r for r in row if r]
        row.extend(self._get_statistics(nonzero_row))
        return dict(
            numerators=self._format_row(row)
        )