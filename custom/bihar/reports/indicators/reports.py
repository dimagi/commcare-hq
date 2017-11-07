from __future__ import absolute_import
import logging
from custom.bihar.reports.supervisor import BiharNavReport, MockEmptyReport, \
    url_and_params, BiharSummaryReport, \
    ConvenientBaseMixIn, GroupReferenceMixIn, list_prompt, shared_bihar_context,\
    team_member_context
from copy import copy
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.generic import GenericTabularReport, summary_context
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.html import format_html
from django.utils.translation import ugettext as _, ugettext_noop
from custom.bihar.reports.indicators.mixins import IndicatorSetMixIn, IndicatorMixIn
from custom.bihar.utils import groups_for_user, get_all_owner_ids_from_group

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
    def _headers(self):
        return {
            'supervisor': [_("Team Name")] + [_(i.name) for i in self.data_provider.summary_indicators],
            'manager': [_("Subcentre")] + [_(i.name) for i in self.data_provider.summary_indicators],
        }
    
    @property
    @memoized
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params['indicator'] = indicator.slug
            del params['next_report']
            return format_html(u'{chart}<a href="{next}">{val}</a>',
                val=self.data_provider.get_indicator_value(indicator),
                chart=self.data_provider.get_chart(indicator),
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain,
                                                render_as=self.render_next),
                    params,
            ))

        return [self.group_display] + \
               [_nav_link(i) for i in self.data_provider.summary_indicators]


class MyPerformanceReport(BiharSummaryReport):
    name = ugettext_noop('My Performance')
    slug = 'myperformance'
    description = "My performance indicators report"
    set_slug = 'homevisit'  # hard coded to homevisit indicators
    base_template_mobile = "bihar/indicator_summary.html"

    def __init__(self, *args, **kwargs):
        from custom.bihar.reports.indicators.indicators import IndicatorConfig, INDICATOR_SETS
        from custom.bihar.reports.indicators.indicators import IndicatorDataProvider
        self.indicator_set = IndicatorConfig(INDICATOR_SETS).get_indicator_set(self.set_slug)
        super(MyPerformanceReport, self).__init__(*args, **kwargs)
        groups = groups_for_user(self.request.couch_user, self.domain)
        self.data_provider = IndicatorDataProvider(
            self.domain, self.indicator_set, groups,
        )

    @property
    def _headers(self):
        return [_(i.name) for i in self.data_provider.summary_indicators]

    @property
    @memoized
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params["indicators"] = self.set_slug
            params['indicator'] = indicator.slug
            return format_html(u'{chart}<a href="{next}">{val}</a>',
                val=self.data_provider.get_indicator_value(indicator),
                chart=self.data_provider.get_chart(indicator),
                next=url_and_params(
                    MyPerformanceList.get_url(domain=self.domain,
                                              render_as=self.render_next),
                    params,
                )
            )

        return [_nav_link(i) for i in self.data_provider.summary_indicators]


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

    extra_context_providers = [shared_bihar_context, name_context]

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
            reduce=False,
        )

    @property
    @memoized
    def verbose_results(self):
        return self.indicator.fluff_calculator.aggregate_results(
            ([self.domain, owner_id] for owner_id in self.all_owner_ids),
            reduce=False,
            verbose_results=True,
        )

    @property
    def rows(self):
        results = self.verbose_results[self.indicator.fluff_calculator.primary]
        numerators = self.verbose_results['numerator']

        def _reconcile(numerators, denominators):
            def _is_match(num, denom):
                return num['id'] == denom['id'] and num['key'][-1] == denom['key'][-1]

            num_copy = copy(numerators)
            for denom in denominators:
                denom['in_num'] = False
                for num in num_copy:
                    if _is_match(num, denom):
                        num_copy.remove(num)
                        denom['in_num'] = True
                        break
            if num_copy:
                logging.error('expected no indicators left in the numerator but found some')

        def _key(result):
            return (result['in_num'], result['key'][-1])

        _reconcile(numerators, results)
        results = sorted(results, key=_key)
        case_ids = set([res['id'] for res in results])
        cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=list(case_ids),
                                                           include_docs=True))

        return [
            self.indicator.as_row(cases[result['id']], self.fluff_results, fluff_row=result)
            for result in results
        ]


class MyPerformanceList(IndicatorClientList):
    slug = "myperformancelist"

    @property
    def rendered_report_title(self):
        return 'My Performance Clients'

    # hack this a bit to not have to reimplement everything else
    @property
    @memoized
    def all_owner_ids(self):
        groups = groups_for_user(self.request.couch_user, self.domain)
        return set([id for group in groups for id in get_all_owner_ids_from_group(group)])
