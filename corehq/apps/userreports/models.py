from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import Document, StringListProperty
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.factory import FilterFactory, IndicatorFactory
from corehq.apps.userreports.filters import SinglePropertyValueFilter
from corehq.apps.userreports.getters import DictGetter
from corehq.apps.userreports.indicators import CompoundIndicator, ConfigurableIndicatorMixIn
from corehq.apps.userreports.logic import EQUAL
from corehq.apps.userreports.reports.factory import ReportFactory
from django.utils.translation import ugettext as _
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from fluff.filters import ANDFilter


class IndicatorConfiguration(ConfigurableIndicatorMixIn, Document):

    domain = StringProperty(required=True)
    referenced_doc_type = StringProperty(required=True)
    table_id = StringProperty(required=True)
    display_name = StringProperty()
    configured_filter = DictProperty()
    configured_indicators = ListProperty()

    @property
    def filter(self):
        extras = [FilterFactory.from_spec(self.configured_filter)] if self.configured_filter else []
        return ANDFilter([
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
        ] + extras
        )

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

    def get_columns(self):
        return self.indicators.get_columns()

    def get_values(self, item):
        if self.filter.filter(item):
            return self.indicators.get_values(item)
        else:
            return []

    def validate(self, required=True):
        super(IndicatorConfiguration, self).validate(required)
        # these two functions implicitly call other validation
        self.filter
        self.indicators

    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/indicator_configs_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda config: config.display_name
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/indicator_configs_by_domain', reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)


class ReportConfiguration(Document):
    domain = StringProperty(required=True)
    config_id = StringProperty(required=True)
    display_name = StringProperty()
    description = StringProperty()
    aggregation_columns = StringListProperty()
    filters = ListProperty()
    columns = ListProperty()
    graphs = ListProperty()

    @property
    @memoized
    def config(self):
        try:
            return IndicatorConfiguration.get(self.config_id)
        except ResourceNotFound:
            raise BadSpecError(_('The data source referenced by this report could not be found.'))

    @property
    def table_id(self):
        return self.config.table_id

    def validate(self, required=True):
        super(ReportConfiguration, self).validate(required)
        # this implicitly does validation
        ReportFactory.from_spec(self)

    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/report_configs_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda report: report.display_name,
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/report_configs_by_domain', reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)
