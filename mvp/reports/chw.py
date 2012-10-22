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
            for slug in section.get('keys', []):
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
                    expected=section.get('expected', [])[j]
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
                    value = indicator.get_totals(user.get('user_id'), self.datespan)
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
                        v_text = "%d" % value

                    if v > avg+(std*2) and v is not None:
                        # more than two stds above average
                        v_text = mark_safe('<span class="label label-success">%s</span>' % v_text)
                    elif v < avg-(std*2) and v is not None:
                        # more than two stds below average
                        v_text = mark_safe('<span class="label label-important">%s</span>' % v_text)

                    row.append(self.table_cell(v, v_text))
            rows.append(row)

        for section in self.indicators:
            for indicator in section:
                avg = averages[indicator.slug]
                mdn = median[indicator.slug]
                std = std_dev[indicator.slug]
                if issubclass(indicator.__class__, CombinedCouchViewIndicatorDefinition):
                    _fmt = lambda x: "%.f%%" % x
                else:
                    _fmt = lambda x: "%.f" % x
                self.statistics_rows[0].append(self.table_cell(avg, _fmt(avg)))
                self.statistics_rows[1].append(self.table_cell(mdn, _fmt(mdn)))
                self.statistics_rows[2].append(self.table_cell(std, _fmt(std)))

        return rows

    @property
    def indicator_slugs(self):
        return [
            dict(
                title="Household",
                keys=[
                    "num_active_households",
                    "num_household_visits",
                    "households_routine_visit_past90days",
                    "households_routine_visit_past30days"
                ],
                expected=[
                    "--",
                    "--",
                    100,
                    100
                ]
            ),
            dict(
                title="Newborn",
                keys=[
                    "num_births_registered",
                    "facility_births_proportion",
                    "newborn_visit_proportion",
                    "neonate_routine_visit_past7days"
                ],
                expected=[
                    "--",
                    100,
                    100,
                    100
                ]
            ),
            dict(
                title="Under-5s",
                keys=[
                    "num_under5",
                    "under5_danger_signs",
                    "under5_fever",
                    "under5_fever_rdt",
                    "under5_fever_rdt_positive",
                    "under5_fever_rdt_positive_medicated",
                    "under5_diarrhea",
                    "under5_diarrhea_ors",
                    "muac_routine_proportion",
                    "under5_routine_visit_past30days"
                ],
                expected=[
                    "--",
                    "--",
                    "--",
                    100,
                    100,
                    100,
                    "--",
                    100,
                    100,
                    100
                ]
            ),
            dict(
                title="Pregnant",
                keys=[
                    "num_active_pregnancies",
                    "anc4_proportion",
                    "pregnant_routine_visit_past30days"
                ],
                expected=[
                    "--",
                    100,
                    100
                ]
            ),
            dict(
                title="Family Planning",
                keys=[
                    "family_planning_households"
                ],
                expected=[
                    100
                ]
            )
        ]

