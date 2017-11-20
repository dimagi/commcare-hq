from __future__ import absolute_import
from dimagi.utils.decorators.memoized import memoized


class IndicatorConfigMixIn(object):

    @property
    @memoized
    def indicator_config(self):
        from custom.bihar.reports.indicators.indicators import INDICATOR_SETS, IndicatorConfig
        return IndicatorConfig(INDICATOR_SETS)


class IndicatorSetMixIn(object):
    
    @property
    def indicator_set_slug(self):
        return self.request_params.get("indicators")
    
    @property
    @memoized
    def indicator_set(self):
        from custom.bihar.reports.indicators.indicators import INDICATOR_SETS, IndicatorConfig
        return IndicatorConfig(INDICATOR_SETS).get_indicator_set(self.indicator_set_slug)


class IndicatorMixIn(IndicatorSetMixIn):
    
    @property
    def indicator_slug(self):
        return self.request_params.get("indicator")

    @property
    @memoized
    def indicator(self):
        return self.indicator_set.get_indicator(self.indicator_slug)
