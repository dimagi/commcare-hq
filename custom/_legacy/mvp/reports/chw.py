from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
import logging
import numpy
from corehq.apps.indicators.models import DynamicIndicatorDefinition, CombinedCouchViewIndicatorDefinition
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from mvp.models import MVP
from mvp.reports import MVPIndicatorReport

class CHWManagerReport(GenericTabularReport, MVPIndicatorReport, DatespanMixin):
    slug = "chw_manager"
    name = "CHW Manager Report"
    report_template_path = "mvp/reports/chw_report.html"
    fix_left_col = True
    emailable = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    @property
    @memoized
    def template_report(self):
        if self.is_rendered_as_email:
            self.report_template_path ="reports/async/tabular.html"
        return super(CHWManagerReport, self).template_report

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
                    if indicator is not None:
                        section_indicators.append(indicator)
                    else:
                        logging.error("could not load indicator %s" % slug)
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
                    expected=section.get('indicators', [])[j].get('expected'),
                ))
            sections.append(col_group)
        return DataTablesHeader(
            chw,
            *sections
        )

    @property
    def report_context(self):
        context = super(CHWManagerReport, self).report_context
        indicators = []
        index = 0
        for section in self.indicators:
            for indicator in section:
                indicators.append({
                    'slug': indicator.slug,
                    'load_url': "%s?indicator=%s" % (self.get_url(self.domain, render_as='partial'), indicator.slug),
                    'index': index,
                })
                index += 1

        context.update(
            indicators=indicators,
        )
        return context


    @property
    def rows(self):
        self.statistics_rows = [["Average"], ["Median"], ["Std. Dev."], ["Totals"]]
        if self.is_rendered_as_email:
            return self.full_rows
        return self.piecewise_rows

    @property
    def piecewise_rows(self):
        rows = []
        d_text = lambda slug: format_html('<i class="icon icon-spinner status-{0}"></i>', slug)

        def _create_stat_cell(stat_type, slug):
            stat_cell = self.table_cell(None, d_text(slug))
            stat_cell.update(
                css_class="%s %s" % (stat_type, slug),
            )
            return stat_cell

        for section in self.indicators:
            for indicator in section:
                self.statistics_rows[0].append(_create_stat_cell('average', indicator.slug))
                self.statistics_rows[1].append(_create_stat_cell('median', indicator.slug))
                self.statistics_rows[2].append(_create_stat_cell('std', indicator.slug))
                self.statistics_rows[3].append(_create_stat_cell('total', indicator.slug))

        for u, user in enumerate(self.users):
            row_data = [user.get('username_in_report')]
            for section in self.indicators:
                for indicator in section:
                    table_cell = self.table_cell(None, d_text(indicator.slug))
                    table_cell.update(
                        css_class=indicator.slug
                    )
                    row_data.append(table_cell)

            rows.append({
                'data': row_data,
                'css_id': user.get('user_id'),
            })

        return rows


    @property
    @memoized
    def full_rows(self):
        user_data = {}
        for user in self.users:
            user_data[user.get('user_id')] = [user.get('username_in_report')]

        for section in self.indicators:
            for indicator in section:
                indicator_stats = self.get_response_for_indicator(indicator)
                for user_id in self.user_ids:
                    user_data[user_id].append(indicator_stats['data'][user_id])

                self.statistics_rows[0].append(indicator_stats['average'])
                self.statistics_rows[1].append(indicator_stats['median'])
                self.statistics_rows[2].append(indicator_stats['std'])
                self.statistics_rows[3].append(indicator_stats['total'])

        return user_data.values()


    @property
    def indicator_slugs(self):
        return [
            dict(
                title="Household",
                indicators=[
                    dict(slug="household_cases", expected="--"),
                    dict(slug="household_visits", expected="--"),
                    dict(slug="households_routine_visit_past90days", expected="100%"),
                    dict(slug="households_routine_visit_past30days", expected="100%"),
                ]
            ),
            dict(
                title="Newborn",
                indicators=[
                    dict(slug="num_births_occured", expected="--"),
                    dict(slug="num_births_recorded", expected="--"),
                    dict(slug="facility_births_proportion", expected="100%"),
                    dict(slug="newborn_7day_visit_proportion", expected="100%"),
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
                    dict(slug="under5_routine_visit_past30days", expected="100%"),
                    dict(slug="active_gam_cases", expected="--"),
                    dict(slug="under1_immunized_proportion", expected="--"),
                ]
            ),
            dict(
                title="Pregnant",
                indicators=[
                    dict(slug="pregnancy_cases", expected="--"),
                    dict(slug="pregnancy_visit_danger_sign_referral_proportion", expected="100%"),
                    dict(slug="anc4_proportion", expected="100%"),
                    dict(slug="pregnant_routine_checkup_proportion_6weeks", expected="100%"),
                    dict(slug="pregnant_routine_visit_past30days", expected="100%"),
                    ]
            ),
            dict(
                title="Follow-up",
                indicators=[
                    dict(slug="num_urgent_referrals", expected="--"), # denominator for MVIS indicator
                    dict(slug="urgent_referrals_proportion", expected="100%"), # MVIS Indicator
                    dict(slug="late_followups_proportion", expected="--"),
                    dict(slug="no_followups_proportion", expected="--"),
                    dict(slug="median_days_referral_followup", expected="<=2"),
                ]
            ),
            dict(
                title="Family Planning",
                indicators=[
                    dict(slug="household_num_ec", expected="--"),
                    dict(slug="family_planning_proportion", expected="100%"),
                    ]
            ),
            dict(
                title="Stats",
                indicators=[
                    dict(slug="days_since_last_transmission", expected="--"),
                ]
            )
        ]

    def get_response_for_indicator(self, indicator):
        raw_values = {}
        user_indices = {}
        formatted_values = {}

        def _formatted_cell(val, val_text):
            table_cell = self.table_cell(val, val_text)
            table_cell.update(
                unwrap=True,
                )
            return render_to_string("reports/async/partials/tabular_cell.html", { 'col': table_cell })

        if issubclass(indicator.__class__, CombinedCouchViewIndicatorDefinition):
            _fmt_stat = lambda x: "%.f%%" % x if not numpy.isnan(x) else "--"
        else:
            _fmt_stat = lambda x: "%.f" % x if not numpy.isnan(x) else "--"

        for u, user in enumerate(self.users):
            self.datespan.inclusive = False
            value = indicator.get_value([user.get('user_id')], self.datespan)
            raw_values[user.get('user_id')] = value
            user_indices[user.get('user_id')] = u
        all_values = raw_values.values()
        if all_values:
            if isinstance(all_values[0], dict):
                non_zero = [v.get('ratio') * 100 for v in all_values if v.get('ratio') is not None]
                d_nonzero = [v.get('denominator') for v in all_values if v.get('ratio') is not None]
                n_nonzero = [v.get('numerator') for v in all_values if v.get('ratio') is not None]
                d_sum = sum(d_nonzero)
                n_sum = sum(n_nonzero)
                total_ratio = float(n_sum) / float(d_sum) * 100 if d_sum > 0 else None
                total = "%.f%% (%d/%d)" % (total_ratio, n_sum, d_sum) if total_ratio is not None else "---"
            else:
                non_zero = [v for v in all_values if v > 0]
                nz_sum = sum(non_zero)
                total = _formatted_cell(nz_sum, _fmt_stat(nz_sum))

            avg = numpy.average(non_zero)
            median = numpy.median(non_zero)
            std = numpy.std(non_zero)

            for user_id, value in raw_values.items():
                if isinstance(value, dict):
                    ratio = value.get('ratio')
                    v = ratio*100 if ratio else None
                    v_text = "%.f%% (%d/%d)" % ((ratio*100), value.get('numerator'), value.get('denominator')) if ratio is \
                        not None else "--"
                else:
                    v = value
                    v_text = "%d" % value if value is not None else "--"

                if v > avg+(std*2) and v is not None:
                    # more than two stds above average
                    v_text = mark_safe('<span class="label label-success">%s</span>' % v_text)
                elif v < avg-(std*2) and v is not None:
                    # more than two stds below average
                    v_text = mark_safe('<span class="label label-important">%s</span>' % v_text)

                formatted_values[user_id] = _formatted_cell(v, v_text)
        else:
            total = avg = median = std = 0

        return {
            'slug': indicator.slug,
            'data': formatted_values,
            'user_indices': user_indices,
            'total': total,
            'average': _formatted_cell(avg, _fmt_stat(avg)),
            'median': _formatted_cell(median, _fmt_stat(median)),
            'std': _formatted_cell(std, _fmt_stat(std))
        }
