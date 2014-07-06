from couchdbkit import Document
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from corehq.apps.userreports.factory import FilterFactory, IndicatorFactory
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.getters import DictGetter
from corehq.apps.userreports.logic import EQUAL
from fluff.filters import ANDFilter


class IndicatorConfiguration(Document):

    domain = StringProperty()
    doc_type = StringProperty()
    table_id = StringProperty()
    _filter = DictProperty()
    _indicators = ListProperty()

    @property
    def filter(self):
        return ANDFilter([
            FilterFactory.from_spec(self._filter),
            SinglePropertyValueFilter(
                getter=DictGetter('domain'),
                operator=EQUAL,
                reference_value=self.domain
            ),
            SinglePropertyValueFilter(
                getter=DictGetter('doc_type'),
                operator=EQUAL,
                reference_value=self.doc_type
            ),
        ])

    @property
    def indicators(self):
        return [IndicatorFactory.from_spec(indicator) for indicator in self._indicators]
