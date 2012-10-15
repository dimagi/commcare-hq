from bihar.reports.supervisor import MockNavReport, MockEmptyReport,\
    url_and_params, SubCenterSelectionReport, TeamHoldingMixIn
from bihar.reports.indicators import INDICATOR_SETS, IndicatorConfig
from copy import copy

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
    

class IndicatorNav(MockNavReport):
    name = "Indicator Options"
    slug = "indicatornav"
    description = "Indicator navigation"
    preserve_url_params = True
    
    @property
    def reports(self):
        return [IndicatorSummaryReport, IndicatorClientList, 
                IndicatorCharts]

class IndicatorSelectNav(MockEmptyReport, IndicatorConfigMixIn):
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
            params["next_report"] = IndicatorSummaryReport.slug
            return '<a href="%(next)s">%(val)s</a>' % \
                {"val": indicator_set.name,
                 "next": url_and_params(
                    SubCenterSelectionReport.get_url(self.domain, 
                                                     render_as=self.render_next),
                    params
                )}
        return [_nav_link(iset) for iset in self.indicator_config.indicator_sets]

    
class IndicatorSummaryReport(MockEmptyReport, IndicatorSetMixIn, TeamHoldingMixIn):
    name = "Indicators"
    slug = "indicatorsummary"
    description = "Indicator details report"
    
    @property
    def _headers(self):
        return ["Team Name"] + [i.name for i in self.indicator_set.indicators]
    
    @property
    def data(self):
        return [self.team] + \
               [self.fake_done_due(i) for i in range(len(self._headers) - 1)]

class IndicatorClientList(MockEmptyReport):
    name = "Client Lists"
    slug = "indicatorclientlist"

class IndicatorCharts(MockEmptyReport):
    name = "Charts"
    slug = "indicatorcharts"

