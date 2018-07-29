from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import timedelta
from dimagi.ext.couchdbkit import Document
import fluff


class _(Document):
    pass


class SimpleCalculator(fluff.Calculator):
    """
    By default just emits a single "total" value for anything matching the filter,
    though additional fields can be added by subclassing.

    Emitting a specific value and a custom group_by clause can be accomplished by
    using the "indicator_calculator" and "group_by_provider".
    """
    window = timedelta(days=1)
    date_provider = None
    indicator_calculator = None
    group_by_provider = None
    _filter = None

    def __init__(self, date_provider=None, filter=None,
                 indicator_calculator=None, group_by_provider=None, window=None):
        super(SimpleCalculator, self).__init__(filter=filter, window=window)
        self.date_provider = date_provider
        assert self.date_provider is not None

        def _conditional_setattr(key, value):
            if value:
                setattr(self, key, value)

        _conditional_setattr('_filter', filter)
        _conditional_setattr('indicator_calculator', indicator_calculator)
        _conditional_setattr('group_by_provider', group_by_provider)

    @fluff.date_emitter
    def total(self, doc):
        if self.group_by_provider:
            ret = dict(
                date=self.date_provider(doc),
                group_by=self.group_by_provider(doc)
            )
            if self.indicator_calculator:
                ret['value'] = self.indicator_calculator(doc)

            yield ret
        if not self.indicator_calculator:
            yield self.date_provider(doc)
        elif not self.group_by_provider:
            yield [self.date_provider(doc), self.indicator_calculator(doc)]
