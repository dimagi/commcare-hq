from bihar.reports.supervisor import MockNavReport, MockEmptyReport,\
    url_and_params, SubCenterSelectionReport, TeamHoldingMixIn,\
    MockSummaryReport, MockTablularReport, ConvenientBaseMixIn,\
    GroupReferenceMixIn
from bihar.reports.indicators import INDICATOR_SETS, IndicatorConfig
from copy import copy
from dimagi.utils.html import format_html
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from casexml.apps.case.models import CommCareCase

DEFAULT_EMPTY = "?"

class IndicatorConfigMixIn(object):
    @property
    def indicator_config(self):
        return IndicatorConfig(INDICATOR_SETS)
    
class IndicatorSetMixIn(object):
    
    @property
    def indicator_set_slug(self):
        return self.request_params.get("indicators")
    
    @property
    def indicator_set(self):
        return IndicatorConfig(INDICATOR_SETS).get_indicator_set(self.indicator_set_slug)

class IndicatorMixIn(IndicatorSetMixIn):
    
    @property
    def type_slug(self):
        return self.request_params.get("indicator_type")

    @property
    def indicator_slug(self):
        return self.request_params.get("indicator")

    @property
    def indicator(self):
        return self.indicator_set.get_indicator(self.type_slug, self.indicator_slug)
        
        
class IndicatorNav(MockNavReport):
    name = "Indicator Options"
    slug = "indicatornav"
    description = "Indicator navigation"
    preserve_url_params = True
    
    @property
    def reports(self):
        return [IndicatorSummaryReport, IndicatorClientSelectNav, 
                IndicatorCharts]

class IndicatorSelectNav(MockSummaryReport, IndicatorConfigMixIn):
    name = "Select Team"
    slug = "teams"
    
    @property
    def _headers(self):
        return [" "] * len(self.indicator_config.indicator_sets)
    
    @property
    def data(self):
        def _nav_link(indicator_set):
            params = copy(self.request_params)
            params["indicators"] = indicator_set.slug
            params["next_report"] = IndicatorNav.slug
            return format_html('<a href="{next}">{val}</a>',
                val=indicator_set.name,
                next=url_and_params(
                    SubCenterSelectionReport.get_url(self.domain, 
                                                     render_as=self.render_next),
                    params
                ))
        return [_nav_link(iset) for iset in self.indicator_config.indicator_sets]

    
class IndicatorSummaryReport(MockSummaryReport, IndicatorSetMixIn, TeamHoldingMixIn):
    name = "Indicators"
    slug = "indicatorsummary"
    description = "Indicator details report"
    
    @property
    def _headers(self):
        return ["Team Name"] + [i.name for i in self.indicator_set.get_indicators("summary")]
    
    @property
    def data(self):
        return [self.team] + \
               [self.fake_done_due(i) for i in range(len(self._headers) - 1)]


class IndicatorCharts(MockEmptyReport):
    name = "Charts"
    slug = "indicatorcharts"



class IndicatorClientSelectNav(MockSummaryReport, IndicatorSetMixIn):
    name = "Select Client List"
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
        def _nav_link(indicator):
            params = copy(self.request_params)
            params["indicators"] = self.indicator_set.slug
            params["indicator"] = indicator.slug
            params["indicator_type"] = self._indicator_type
            # params["next_report"] = IndicatorNav.slug
            return format_html('<a href="{next}">{val}</a>',
                val=indicator.name,
                next=url_and_params(
                    IndicatorClientList.get_url(self.domain, 
                                                render_as=self.render_next),
                    params
                ))
        return [_nav_link(iset) for iset in self.indicators]


class IndicatorClientList(ConvenientBaseMixIn, GenericTabularReport, 
                          CustomProjectReport, GroupReferenceMixIn,
                          IndicatorMixIn):
    slug = "indicatorclientlist"
    
    @property
    def name(self):
        try:
            return self.indicator.name
        except AttributeError:
            return "Client List" 

    _headers = ["Name", "EDD"] 
    
    
    def _filter(self, case):
        if self.indicator and self.indicator.filter_function:
            return self.indicator.filter_function(case)
        else:
            return True
    
    def _get_clients(self):
        cases = CommCareCase.view('case/by_owner', key=[self.group_id, False],
                                  include_docs=True, reduce=False)
        for c in cases:
            if self._filter(c):
                yield c
        
    @property
    def rows(self):
        return [[c.name, getattr(c, 'edd', DEFAULT_EMPTY)] for c in self._get_clients()]
        
