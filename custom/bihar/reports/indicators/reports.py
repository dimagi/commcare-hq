from functools import partial
from custom.bihar.reports.supervisor import BiharNavReport, MockEmptyReport, \
    url_and_params, BiharSummaryReport, \
    ConvenientBaseMixIn, GroupReferenceMixIn, list_prompt, shared_bihar_context,\
    team_member_context
from copy import copy
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.generic import GenericTabularReport, summary_context
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from django.utils.translation import ugettext as _, ugettext_noop
from custom.bihar.reports.indicators.mixins import IndicatorSetMixIn, IndicatorMixIn

DEFAULT_EMPTY = "?"


class IndicatorNav(GroupReferenceMixIn, BiharNavReport):
    name = ugettext_noop("Indicator Options")
    slug = "indicatornav"
    description = ugettext_noop("Indicator navigation")
    preserve_url_params = True
    report_template_path = "bihar/team_listing_tabular.html"
    
    extra_context_providers = [shared_bihar_context, summary_context, team_member_context]
    @property
    def reports(self):
        return [IndicatorClientSelectNav, IndicatorSummaryReport]

    @property
    def rendered_report_title(self):
        return self.group_display


class IndicatorSummaryReport(GroupReferenceMixIn, BiharSummaryReport,
                             IndicatorSetMixIn):
    
    name = ugettext_noop("Indicators")
    slug = "indicatorsummary"
    description = "Indicator details report"
    base_template_mobile = "bihar/indicator_summary.html"
    is_cacheable = True

    def __init__(self, *args, **kwargs):
        super(IndicatorSummaryReport, self).__init__(*args, **kwargs)
        from custom.bihar.reports.indicators.indicators import IndicatorDataProvider
        self.data_provider = IndicatorDataProvider(
            self.domain, self.indicator_set, [self.group],
        )

    @property
    def rendered_report_title(self):
        return _(self.indicator_set.name)

    @property
    def summary_indicators(self):
        return self.data_provider.summary_indicators

    @property
    def _headers(self):
        return {
            'supervisor': [_("Team Name")] + [_(i.name) for i in self.summary_indicators],
            'manager': [_("Subcentre")] + [_(i.name) for i in self.summary_indicators],
        }
    
    @property
    @memoized
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params['indicator'] = indicator.slug
            del params['next_report']
            return format_html(u'{chart}<a href="{next}">{val}</a>',
                val=self.get_indicator_value(indicator),
                chart=self.get_chart(indicator),
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain, 
                                                render_as=self.render_next),
                    params
            ))

        return [self.group_display] + \
               [_nav_link(i) for i in self.summary_indicators]

    @memoized
    def get_indicator_value(self, indicator):
        return "%s/%s" % self.data_provider.get_indicator_data(indicator)

    def get_chart(self, indicator):
        # this is a serious hack for now
        pie_class = 'sparkpie'
        split = self.get_indicator_value(indicator).split("/")
        chart_template = (
            '<span data-numerator="{num}" '
            'data-denominator="{denom}" class="{pie_class}"></span>'
        )
        if len(split) == 2:
            return format_html(chart_template, num=split[0],
                               denom=int(split[1]) - int(split[0]),
                               pie_class=pie_class)
        return ''  # no chart


class MyPerformanceReport(IndicatorSummaryReport):
    name = ugettext_noop('My Performance')
    slug = 'myperformance'
    description = "My performance indicators report"


class IndicatorCharts(MockEmptyReport):
    name = ugettext_noop("Charts")
    slug = "indicatorcharts"


class IndicatorClientSelectNav(GroupReferenceMixIn, BiharSummaryReport,
                               IndicatorSetMixIn):
    name = ugettext_noop("Select Client List")
    slug = "clients"
    is_cacheable = True
    
    _indicator_type = "client_list"

    @property
    def rendered_report_title(self):
        return self.group_display

    @property
    def indicators(self):
        return [i for i in self.indicator_set.get_indicators() if i.show_in_client_list]
    
    @property
    def _headers(self):
        return [list_prompt(i, iset.name) for i, iset in enumerate(self.indicators)]

    @property
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params["indicators"] = self.indicator_set.slug
            params["indicator"] = indicator.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=self.count(indicator),
                next=url_and_params(
                    IndicatorClientList.get_url(domain=self.domain,
                                                render_as=self.render_next),
                    params
                ))

        return [_nav_link(i) for i in self.indicators]

    def count(self, indicator):
        def totals():
            for owner_id in self.all_owner_ids:
                calculator = indicator.fluff_calculator
                yield calculator.get_result(
                    [self.domain, owner_id]
                )['total']
        return sum(totals())


def name_context(report):
    return {'name': report._name}


class ClientListBase(GroupReferenceMixIn, ConvenientBaseMixIn,
                     GenericTabularReport, CustomProjectReport):
    # "abstract" class for client list reports
    report_template_path = "bihar/client_listing.html"

class IndicatorClientList(ClientListBase, IndicatorMixIn):
    is_cacheable = True
    slug = "indicatorclientlist"
    name = ugettext_noop("Client List") 

    extra_context_providers = [name_context]

    @property
    def _name(self):
        # NOTE: this isn't currently used, but is how things should work
        # once we have a workaround for name needing to be available at
        # the class level.
        try:
            return self.indicator.name
        except AttributeError:
            return self.name

    @property
    def _headers(self):
        return [_(c) for c in self.indicator.get_columns()]

    @property
    def headers(self):
        headers = super(IndicatorClientList, self).headers
        headers.custom_sort = [self.indicator.sort_index]
        return headers

    @property
    @memoized
    def fluff_results(self):
        return self.indicator.fluff_calculator.aggregate_results(
            ([self.domain, owner_id] for owner_id in self.all_owner_ids),
            reduce=False
        )

    @property
    def rows(self):
        case_ids = self.fluff_results[self.indicator.fluff_calculator.primary]
        cases = CommCareCase.view('_all_docs', keys=list(case_ids),
                                  include_docs=True)

        return [
            self.indicator.as_row(case, self.fluff_results)
            for case in sorted(
                cases,
                key=partial(self.indicator.sortkey, context=self.fluff_results)
            )
        ]
