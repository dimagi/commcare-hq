from bihar.reports.supervisor import BiharNavReport, MockEmptyReport, \
    url_and_params, BiharSummaryReport, \
    ConvenientBaseMixIn, GroupReferenceMixIn, list_prompt, shared_bihar_context,\
    team_member_context
from copy import copy
from corehq.apps.reports.generic import GenericTabularReport, summary_context
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from django.utils.translation import ugettext as _, ugettext_noop
from bihar.reports.indicators.mixins import IndicatorSetMixIn, IndicatorMixIn

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
        return [IndicatorClientSelectNav, IndicatorSummaryReport,
                # IndicatorCharts
                ]

class IndicatorSummaryReport(GroupReferenceMixIn, BiharSummaryReport, IndicatorSetMixIn):
    
    name = ugettext_noop("Indicators")
    slug = "indicatorsummary"
    description = "Indicator details report"

    @property
    def summary_indicators(self):
        return [i for i in self.indicator_set.get_indicators() if i.show_in_indicators]
    
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
        return indicator.calculation_class.display(self.cases)
    
class IndicatorCharts(MockEmptyReport):
    name = ugettext_noop("Charts")
    slug = "indicatorcharts"


class IndicatorClientSelectNav(GroupReferenceMixIn, BiharSummaryReport, IndicatorSetMixIn):
    name = ugettext_noop("Select Client List")
    slug = "clients"
    
    _indicator_type = "client_list"
    @property
    def indicators(self):
        return [i for i in self.indicator_set.get_indicators() if i.show_in_client_list]
    
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
        return [_(c) for c in self.indicator.get_columns()]

    @property
    def sorted_cases(self):
        return sorted(self.cases, key=self.indicator.calculation_class.sortkey)
        
    def _filter(self, case):
        if self.indicator:
            return self.indicator.calculation_class.filter(case)
        else:
            return True
    
    def _get_clients(self):
        for c in self.sorted_cases:
            if self._filter(c):
                yield c
        
    @property
    def rows(self):
        return [self.indicator.calculation_class.as_row(c) for c in self._get_clients()]
