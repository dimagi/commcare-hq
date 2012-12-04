from bihar.reports.indicators import INDICATOR_SETS, IndicatorConfig
from bihar.reports.supervisor import BiharNavReport, MockEmptyReport, \
    url_and_params, SubCenterSelectionReport, BiharSummaryReport, \
    ConvenientBaseMixIn, GroupReferenceMixIn, list_prompt
from copy import copy
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from django.utils.translation import ugettext as _, ugettext_noop

DEFAULT_EMPTY = "?"

class IndicatorConfigMixIn(object):
    @property
    @memoized
    def indicator_config(self):
        return IndicatorConfig(INDICATOR_SETS)
    
class IndicatorSetMixIn(object):
    
    @property
    def indicator_set_slug(self):
        return self.request_params.get("indicators")
    
    @property
    @memoized
    def indicator_set(self):
        return IndicatorConfig(INDICATOR_SETS).get_indicator_set(self.indicator_set_slug)

class IndicatorMixIn(IndicatorSetMixIn):
    
    @property
    def indicator_slug(self):
        return self.request_params.get("indicator")

    @property
    @memoized
    def indicator(self):
        return self.indicator_set.get_indicator(self.indicator_slug)
        
        
class IndicatorNav(GroupReferenceMixIn, BiharNavReport):
    name = ugettext_noop("Indicator Options")
    slug = "indicatornav"
    description = ugettext_noop("Indicator navigation")
    preserve_url_params = True
    
    @property
    def reports(self):
        return [IndicatorClientSelectNav, IndicatorSummaryReport,
                # IndicatorCharts
                ]

class IndicatorSelectNav(BiharSummaryReport, IndicatorConfigMixIn):
    name = ugettext_noop("Select Indicator Category")
    slug = "teams"
    
    @property
    def _headers(self):
        return [" "] * len(self.indicator_config.indicator_sets)
    
    @property
    def data(self):
        def _nav_link(i, indicator_set):
            params = copy(self.request_params)
            params["indicators"] = indicator_set.slug
            params["next_report"] = IndicatorNav.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=list_prompt(i, indicator_set.name),
                next=url_and_params(
                    SubCenterSelectionReport.get_url(self.domain, 
                                                     render_as=self.render_next),
                    params
            ))
        return [_nav_link(i, iset) for i, iset in enumerate(self.indicator_config.indicator_sets)]

    
class IndicatorSummaryReport(GroupReferenceMixIn, BiharSummaryReport, IndicatorSetMixIn):
    
    name = ugettext_noop("Indicators")
    slug = "indicatorsummary"
    description = "Indicator details report"

    @property
    def summary_indicators(self):
        return self.indicator_set.get_indicators("summary")
    
    @property
    def _headers(self):
        return [_("Team Name")] + [_(i.name) for i in self.summary_indicators]
    
    @property
    @memoized
    def data(self):
        def _nav_link(indicator):
            params = copy(self.request_params)
            params['indicator'] = indicator.slug
            del params['next_report']
            return format_html(u'<a href="{next}">{val}</a>',
                val=self.get_indicator_value(indicator),
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain, 
                                                render_as=self.render_next),
                    params
            ))
        
        return [self.group.name] + \
               [_nav_link(i) for i in self.summary_indicators]


    def get_indicator_value(self, indicator):
        if indicator.calculation_class:
            print indicator.calculation_class
            return indicator.calculation_class.display(self.cases)
        if indicator.calculation_function:
            return indicator.calculation_function(self.cases)
        return "not available yet"
    
    
class IndicatorCharts(MockEmptyReport):
    name = ugettext_noop("Charts")
    slug = "indicatorcharts"


class IndicatorClientSelectNav(GroupReferenceMixIn, BiharSummaryReport, IndicatorSetMixIn):
    name = ugettext_noop("Select Client List")
    slug = "clients"
    
    _indicator_type = "client_list"
    @property
    def indicators(self):
        return self.indicator_set.get_indicators(self._indicator_type)
    
    @property
    def _headers(self):
        return [" "] * len(self.indicators)
    
    @property
    def data(self):
        def _nav_link(i, indicator):
            params = copy(self.request_params)
            params["indicators"] = self.indicator_set.slug
            params["indicator"] = indicator.slug
            
            # params["next_report"] = IndicatorNav.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=list_prompt(i, indicator.name),
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain, 
                                                render_as=self.render_next),
                    params
                ))
        return [_nav_link(i, iset) for i, iset in enumerate(self.indicators)]


class IndicatorClientList(GroupReferenceMixIn, ConvenientBaseMixIn,
                          GenericTabularReport, CustomProjectReport,
                          IndicatorMixIn):
    slug = "indicatorclientlist"
    name = ugettext_noop("Client List") 
    
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
        return [_(c) for c in self.indicator.columns]

    @property
    def sorted_cases(self):
        if self.indicator.sortkey:
            return sorted(self.cases, key=self.indicator.sortkey, reverse=True)
        
        return self.cases
    
    def _filter(self, case):
        if self.indicator and self.indicator.calculation_class:
            return self.indicator.calculation_class.filter(case)
        if self.indicator and self.indicator.filter_function:
            return self.indicator.filter_function(case)
        else:
            return True
    
    def _get_clients(self):
        for c in self.sorted_cases:
            if self._filter(c):
                yield c
        
    @property
    def rows(self):
        def _row(case):
            if self.indicator.calculation_class:
                return self.indicator.calculation_class.as_row(case)
            else:
                return self.indicator.row_function(case)
        return [_row(c) for c in self._get_clients()]
    
        
