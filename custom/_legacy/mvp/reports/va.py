import datetime
from couchdbkit import ResourceNotFound
import dateutil
from django.utils.safestring import mark_safe
import logging
import numpy
import pytz
from corehq.apps.indicators.models import DynamicIndicatorDefinition, CombinedCouchViewIndicatorDefinition
from dimagi.utils.decorators.memoized import memoized
from mvp.models import MVP
from mvp.reports import MVPIndicatorReport


class VerbalAutopsyReport(MVPIndicatorReport):
    slug = "verbal_autopsy"
    name = "Verbal Autopsy Report"
    report_template_path = "mvp/reports/verbal_autopsy.html"
    flush_layout = True
    hide_filters = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter']
    emailable = True

    @property
    def timezone(self):
        return pytz.utc

    @property
    def num_prev(self):
        try:
            return int(self.request.GET.get('num_prev'))
        except (ValueError, TypeError):
            pass
        return 12

    @property
    def current_month(self):
        try:
            return dateutil.parser.parse(self.request.GET.get('current_month'))
        except (AttributeError, ValueError):
            pass

    @property
    @memoized
    def template_report(self):
        if self.is_rendered_as_email:
            self.report_template_path = "mvp/reports/verbal_autopsy_email.html"
        return super(VerbalAutopsyReport, self).template_report

    @property
    def report_context(self):
        report_matrix = []
        month_headers = None
        for category_group in self.indicator_slugs:
            category_indicators = []
            total_rowspan = 0
            for slug in category_group['indicator_slugs']:
                try:
                    indicator = DynamicIndicatorDefinition.get_current(
                        MVP.NAMESPACE, self.domain, slug,
                        wrap_correctly=True,
                    )
                    if self.is_rendered_as_email:
                        retrospective = indicator.get_monthly_retrospective(user_ids=self.user_ids)
                    else:
                        retrospective = indicator.get_monthly_retrospective(return_only_dates=True)
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
                        table=table,
                        load_url="%s?indicator=%s" % (self.get_url(self.domain,
                                                      render_as='partial'), indicator.slug),
                        rowspan=indicator_rowspan
                    ))
                except (AttributeError, ResourceNotFound):
                    logging.info("Could not grab indicator %s in domain %s" % (slug, self.domain))
            report_matrix.append(dict(
                category_title=category_group['category_title'],
                category_slug=category_group['category_slug'],
                rowspan=total_rowspan,
                indicators=category_indicators,
            ))
        return dict(
            months=month_headers,
            report=report_matrix,
        )

    @property
    def indicator_slugs(self):
        return [
            {
                'category_title': "Reported",
                'category_slug': 'va_reported',
                'indicator_slugs': [
                    "va_reported_stillbirths",
                    "va_reported_neonatesdeaths",
                    "va_reported_1to59deaths",
                    "va_reported_under5deaths",
                    "va_reported_adultdeaths",
                ]
            },
            {
                'category_title': "Observed",
                'category_slug': 'va_observed',
                'indicator_slugs': [
                    "va_observed_stillbirths",
                    "va_observed_neonatesdeaths",
                    "va_observed_1to59deaths",
                    "va_observed_under5deaths",
                    "va_observed_adultdeaths",
                ]
            },
            {
                'category_title': "Location",
                'category_slug': 'va_location',
                'indicator_slugs': [
                    "va_0to59deaths_home",
                    "va_0to59deaths_facility",
                    "va_0to59deaths_hosp",
                    "va_0to59deaths_route",
                ]
            },
            {
                'category_title': "Still Births",
                'category_slug': 'va_stillbirths',
                'indicator_slugs': [
                    "va_stillbirth_deaths",
                ]
            },
            {
                'category_title': "Medical Neonate",
                'category_slug': 'va_neonates',
                'indicator_slugs': [
                    "va_neonates_birth_asphyxia",
                    "va_neonates_birth_trauma",
                    "va_neonates_congenital_abnormality",
                    "va_neonates_neonates_diarrhea_dysentery",
                    "va_neonates_low_birthweight_malnutrition_preterm",
                    "va_neonates_pneumonia_ari",
                    "va_neonates_tetanus",
                    "va_neonates_unknown",
                ]
            },
            {
                'category_title': "Medical Child(1-59)",
                'category_slug': 'va_child',
                'indicator_slugs': [
                    "va_child_accident",
                    "va_child_diarrhea_dysentery",
                    "va_child_persistent_diarrhea_dysentery",
                    "va_child_acute_diarrhea",
                    "va_child_acute_dysentery",
                    "va_child_malaria",
                    "va_child_malnutrition",
                    "va_child_measles",
                    "va_child_meningitis",
                    "va_child_pneumonia_ari",
                    "va_child_unknown",
                ]
            },
            {
                'category_title': "Medical Adult",
                'category_slug': 'va_adult',
                'indicator_slugs': [
                    "va_adult_abortion",
                    "va_adult_accident",
                    "va_adult_antepartum_haemorrhage",
                    "va_adult_postpartum_haemorrhage",
                    "va_adult_eclampsia",
                    "va_adult_obstructed_labour",
                    "va_adult_pleural_sepsis",
                    "va_adult_unknown",
                ]
            },
            {
                'category_title': "Social All",
                'category_slug': 'va_social_all',
                'indicator_slugs': [
                    "va_social_no_formal_healthcare_contact",
                    "va_social_clinicial_unavailable_clinic",
                    "va_social_clinicial_unavailable_hosp",
                    "va_social_financial_barrier",
                    "va_social_access_medication_barrier",
                    "va_social_access_transport_barrier",
                    "va_social_access_communication_barrier",
                    "va_social_personal_healthcare_barrier",
                    "va_social_unmet_referral",
                    "va_social_delay_first_contact_mild",
                    "va_social_delay_first_contact_severe",
                    "va_social_delay_chw_facility_mild",
                    "va_social_delay_chw_facility_severe",
                    "va_social_delay_clinic_hosp_mild",
                    "va_social_delay_clinic_hosp_severe",
                ]
            }
        ]

    def get_month_headers(self, retrospective):
        headers = list()
        month_fmt = "%b %Y"
        num_months = len(retrospective)
        for i, result in enumerate(retrospective):
            month = result.get('date')
            month_text = month.strftime(month_fmt) if isinstance(month, datetime.datetime) else "Unknown"
            month_desc = "(-%d)" % (num_months - (i + 1)) if (num_months - i) > 1 else "(Current)"
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
            n_stats.append(n_row[i])
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
                text = "%.f%%" % (val * 100) if as_percent else "%d" % int(val)
            else:
                text = "--"

            if i == num_cols - 4:
                css = "current_month"
            elif i > num_cols - 4:
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
        if nonzero_row:
            return [numpy.average(nonzero_row), numpy.median(nonzero_row), numpy.std(nonzero_row)]
        return [None] * 3

    def get_indicator_row(self, retrospective):
        row = [i.get('value', 0) for i in retrospective]
        nonzero_row = [r for r in row]
        row.extend(self._get_statistics(nonzero_row))
        return dict(
            numerators=self._format_row(row)
        )

    def get_response_for_indicator(self, indicator):
        retrospective = indicator.get_monthly_retrospective(
            user_ids=self.user_ids,
            is_debug=self.is_debug,
            num_previous_months=self.num_prev,
            current_month=self.current_month,
        )
        if self.is_debug:
            for result in retrospective:
                result['date'] = result['date'].strftime("%B %Y")
            return retrospective
        if isinstance(indicator, CombinedCouchViewIndicatorDefinition):
            table = self.get_indicator_table(retrospective)
        else:
            table = self.get_indicator_row(retrospective)
        return {
            'table': table,
        }
