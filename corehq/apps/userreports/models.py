from couchdbkit import Document
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from corehq.apps.userreports.factory import FilterFactory, IndicatorFactory


class IndicatorConfiguration(Document):

    domain = StringProperty()
    table_id = StringProperty()
    _filter = DictProperty()
    _indicators = ListProperty()

    @property
    def filter(self):
        return FilterFactory.from_spec(self._filter)

    @property
    def indicators(self):
        return [IndicatorFactory.from_spec(indicator) for indicator in self._indicators]
