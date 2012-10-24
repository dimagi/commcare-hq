from django.utils.safestring import mark_safe
import numpy
from corehq.apps.indicators.models import DynamicIndicatorDefinition, CouchViewIndicatorDefinition, CombinedCouchViewIndicatorDefinition
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from mvp.models import MVP
from mvp.reports import MVPIndicatorReport

class CHWManagerReport(GenericTabularReport, MVPIndicatorReport, DatespanMixin):
    slug = "chw_manager"
    name = "CHW Manager Report"
    fix_left_col = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    @property
    @memoized
    def indicators(self):
        all_indicators = list()
        for section in self.indicator_slugs:
            section_indicators = list()
            for indicator_content in section.get('indicators', []):
                slug = indicator_content.get('slug')
                if slug:
                    indicator = DynamicIndicatorDefinition.get_current(MVP.NAMESPACE,
                        self.domain, slug, wrap_correctly=True)
                    section_indicators.append(indicator)
            all_indicators.append(section_indicators)
        return all_indicators

    @property
    def headers(self):
        chw = DataTablesColumn("CHW Name")
        sections = list()
        for i, section in enumerate(self.indicator_slugs):
            col_group = DataTablesColumnGroup(section.get('title', ''))
            for j, indicator in enumerate(self.indicators[i]):
                col_group.add_column(DataTablesColumn(
                    indicator.title or indicator.description,
                    rotate=True,
                    expected=section.get('indicators', [])[j].get('expected')
                ))
            sections.append(col_group)
        return DataTablesHeader(
            chw,
            *sections
        )

    @property
    def rows(self):
        rows = list()

        raw_values = dict()
        for user in self.users:
            for section in self.indicators:
                for indicator in section:
                    if indicator.slug not in raw_values:
                        raw_values[indicator.slug] = list()
                    value = indicator.get_value(user.get('user_id'), self.datespan)
                    raw_values[indicator.slug].append(value)

        averages = dict()
        median = dict()
        std_dev = dict()
        self.statistics_rows = [["Average"], ["Median"], ["Std. Dev."]]
        for slug, values in raw_values.items():
            if isinstance(values[0], dict):
                non_zero = [v.get('ratio')*100 for v in values if v.get('ratio') is not None]
            else:
                non_zero = [v for v in values if v > 0]
            averages[slug] = numpy.average(non_zero)
            median[slug] = numpy.median(non_zero)
            std_dev[slug] = numpy.std(non_zero)

        for u, user in enumerate(self.users):
            row = [user.get('username_in_report')]
            for section in self.indicators:
                for indicator in section:
                    value = raw_values.get(indicator.slug, [])[u]
                    avg = averages[indicator.slug]
                    std = std_dev[indicator.slug]
                    if isinstance(value, dict):
                        ratio = value.get('ratio')
                        v = ratio*100 if ratio else None
                        v_text = "%.f%%" % (ratio*100) if ratio is not None else "--"
                    else:
                        v = value
                        v_text = "%d" % value if value is not None else "--"

                    if v > avg+(std*2) and v is not None:
                        # more than two stds above average
                        v_text = mark_safe('<span class="label label-success">%s</span>' % v_text)
                    elif v < avg-(std*2) and v is not None:
                        # more than two stds below average
                        v_text = mark_safe('<span class="label label-important">%s</span>' % v_text)

                    #for debugging
                    if isinstance(value, dict) and v is not None:
                        v_text = mark_safe("%s<br /> (%d/%d)" % (
                            v_text,
                            value.get('numerator', 0),
                            value.get('denominator', 0)
                        ))

                    row.append(self.table_cell(v, v_text))
            rows.append(row)

        for section in self.indicators:
            for indicator in section:
                avg = averages[indicator.slug]
                mdn = median[indicator.slug]
                std = std_dev[indicator.slug]
                if issubclass(indicator.__class__, CombinedCouchViewIndicatorDefinition):
                    _fmt = lambda x: "%.f%%" % x if not numpy.isnan(x) else "--"
                else:
                    _fmt = lambda x: "%.f" % x if not numpy.isnan(x) else "--"
                self.statistics_rows[0].append(self.table_cell(avg, _fmt(avg)))
                self.statistics_rows[1].append(self.table_cell(mdn, _fmt(mdn)))
                self.statistics_rows[2].append(self.table_cell(std, _fmt(std)))

        return rows

    @property
    def indicator_slugs(self):
        return [
            dict(
                title="Household",
                indicators=[
                    dict(slug="num_active_households", expected="--"),
                    dict(slug="num_household_visits", expected="--"),
                    dict(slug="households_routine_visit_past90days", expected="100%"),
                    dict(slug="households_routine_visit_past30days", expected="100%"),
                ]
            ),
            dict(
                title="Newborn",
                indicators=[
                    dict(slug="num_births_registered", expected="--"),
                    dict(slug="facility_births_proportion", expected="100%"),
                    dict(slug="newborn_visit_proportion", expected="100%"),
                    dict(slug="neonate_routine_visit_past7days", expected="100%"),
                ]
            ),
            dict(
                title="Under-5s",
                indicators=[
                    dict(slug="num_under5", expected="--"),
                    dict(slug="under5_danger_signs", expected="--"),
                    dict(slug="under5_fever", expected="--"),
                    dict(slug="under5_fever_rdt_proportion", expected="100%"),
                    dict(slug="under5_fever_rdt_positive_proportion", expected="100%"),
                    dict(slug="under5_fever_rdt_positive_medicated_proportion", expected="100%"),
                    dict(slug="under5_diarrhea", expected="--"),
                    dict(slug="under5_diarrhea_ors_proportion", expected="100%"),
                    dict(slug="muac_routine_proportion", expected="100%"),
                    dict(slug="num_active_gam", expected="--"),
                    dict(slug="under5_routine_visit_past30days", expected="100%"),
                ]
            ),
            dict(
                title="Pregnant",
                indicators=[
                    dict(slug="num_active_pregnancies", expected="--"),
                    dict(slug="pregnancy_visit_danger_sign_referral_proportion", expected="100%"),
                    dict(slug="anc4_proportion", expected="100%"),
                    dict(slug="pregnant_routine_checkup_proportion", expected="100%"),
                    dict(slug="pregnant_routine_visit_past30days", expected="100%"),
                    ]
            ),
            dict(
                title="Follow-up",
                indicators=[
                    dict(slug="num_urgent_treatment_referral", expected="--"),
                    dict(slug="on_time_followups_proportion", expected="100%"),
                    dict(slug="late_followups_proportion", expected="--"),
                    dict(slug="no_followups_proportion", expected="--"),
                    dict(slug="median_days_followup", expected="<=2"),
                ]
            ),
            dict(
                title="Family Planning",
                indicators=[
                    dict(slug="household_num_ec", expected="--"),
                    dict(slug="family_planning_households", expected="100%"),
                    ]
            ),
            dict(
                title="Stats",
                indicators=[
                    dict(slug="days_since_last_transmission", expected="--"),
                ]
            )
        ]

