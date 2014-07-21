from couchdbkit.ext.django.schema import Document
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from corehq.apps.userreports.factory import FilterFactory, IndicatorFactory
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.getters import DictGetter
from corehq.apps.userreports.indicators import CompoundIndicator, ConfigurableIndicatorMixIn
from corehq.apps.userreports.logic import EQUAL
from dimagi.utils.couch.database import iter_docs
from fluff.filters import ANDFilter


class IndicatorConfiguration(ConfigurableIndicatorMixIn, Document):

    domain = StringProperty()
    referenced_doc_type = StringProperty()
    table_id = StringProperty()
    display_name = StringProperty()
    configured_filter = DictProperty()
    configured_indicators = ListProperty()

    @property
    def filter(self):
        return ANDFilter([
            FilterFactory.from_spec(self.configured_filter),
            SinglePropertyValueFilter(
                getter=DictGetter('domain'),
                operator=EQUAL,
                reference_value=self.domain
            ),
            SinglePropertyValueFilter(
                getter=DictGetter('doc_type'),
                operator=EQUAL,
                reference_value=self.referenced_doc_type
            ),
        ])

    @property
    def indicators(self):
        doc_id_indicator = IndicatorFactory.from_spec({
            "column_id": "doc_id",
            "type": "raw",
            "display_name": "document id",
            "datatype": "string",
            "property_name": "_id",
            "is_nullable": False,
            "is_primary_key": True,
        })
        return CompoundIndicator(
            self.display_name,
            [doc_id_indicator] + [IndicatorFactory.from_spec(indicator) for indicator in self.configured_indicators]
        )

    @classmethod
    def by_domain(cls, domain):
        return cls.view('userreports/by_domain', key=domain, reduce=False, include_docs=True).all()

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/by_domain', reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)

    def get_columns(self):
        return self.indicators.get_columns()

    def get_values(self, item):
        if self.filter.filter(item):
            return self.indicators.get_values(item)
        else:
            return []
