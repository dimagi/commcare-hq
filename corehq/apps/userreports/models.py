from copy import copy
import json
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django.schema import Document, StringListProperty, BooleanProperty
from couchdbkit.ext.django.schema import StringProperty, DictProperty, ListProperty
from jsonobject import JsonObject
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.indicators import CompoundIndicator
from corehq.apps.userreports.reports.factory import ReportFactory, ChartFactory, ReportFilterFactory
from corehq.apps.userreports.reports.specs import FilterSpec
from django.utils.translation import ugettext as _
from corehq.apps.userreports.specs import EvaluationContext
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from django.conf import settings


DELETED_DOC_TYPES = {
    'CommCareCase': [
        'CommCareCase-Deleted',
    ],
    'XFormInstance': [
        'XFormInstance-Deleted',
        'XFormArchived',
        'XFormDeprecated',
    ],
}


class DataSourceConfiguration(UnicodeMixIn, CachedCouchDocumentMixin, Document):
    """
    A data source configuration. These map 1:1 with database tables that get created.
    Each data source can back an arbitrary number of reports.
    """
    domain = StringProperty(required=True)
    referenced_doc_type = StringProperty(required=True)
    table_id = StringProperty(required=True)
    display_name = StringProperty()
    base_item_expression = DictProperty()
    configured_filter = DictProperty()
    configured_indicators = ListProperty()
    named_filters = DictProperty()

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.display_name)

    def filter(self, document):
        filter_fn = self._get_main_filter()
        return filter_fn(document, EvaluationContext(document))

    def deleted_filter(self, document):
        filter_fn = self._get_deleted_filter()
        return filter_fn and filter_fn(document, EvaluationContext(document))

    def _get_main_filter(self):
        return self._get_filter([self.referenced_doc_type])

    def _get_deleted_filter(self):
        if self.referenced_doc_type in DELETED_DOC_TYPES:
            return self._get_filter(DELETED_DOC_TYPES[self.referenced_doc_type])
        return None

    def _get_filter(self, doc_types):
        extras = (
            [self.configured_filter]
            if self.configured_filter else []
        )
        built_in_filters = [
            self._get_domain_filter_spec(),
            {
                'type': 'or',
                'filters': [
                    {
                        'type': 'property_match',
                        'property_name': 'doc_type',
                        'property_value': doc_type,
                    }
                    for doc_type in doc_types
                ],
            },
        ]
        return FilterFactory.from_spec(
            {
                'type': 'and',
                'filters': built_in_filters + extras,
            },
            context=self.named_filter_objects,
        )

    def _get_domain_filter_spec(self):
        return {
            'type': 'property_match',
            'property_name': 'domain',
            'property_value': self.domain,
        }

    @property
    @memoized
    def named_filter_objects(self):
        return {name: FilterFactory.from_spec(filter, {})
                for name, filter in self.named_filters.items()}

    @property
    def indicators(self):
        doc_id_indicator = IndicatorFactory.from_spec({
            "column_id": "doc_id",
            "type": "expression",
            "display_name": "document id",
            "datatype": "string",
            "is_nullable": False,
            "is_primary_key": True,
            "expression": {
                "type": "root_doc",
                "expression": {
                    "type": "property_name",
                    "property_name": "_id"
                }
            }
        }, self.named_filter_objects)
        return CompoundIndicator(
            self.display_name,
            [doc_id_indicator] + [
                IndicatorFactory.from_spec(indicator, self.named_filter_objects)
                for indicator in self.configured_indicators
            ]
        )

    @property
    def parsed_expression(self):
        if self.base_item_expression:
            return ExpressionFactory.from_spec(self.base_item_expression, context=self.named_filter_objects)
        return None

    def get_columns(self):
        return self.indicators.get_columns()

    def get_items(self, document):
        if self.filter(document):
            if not self.base_item_expression:
                return [document]
            else:
                result = self.parsed_expression(document)
                if result is None:
                    return []
                elif isinstance(result, list):
                    return result
                else:
                    return [result]
        else:
            return []

    def get_all_values(self, doc):
        context = EvaluationContext(doc)
        return [self.indicators.get_values(item, context) for item in self.get_items(doc)]

    def validate(self, required=True):
        super(DataSourceConfiguration, self).validate(required)
        # these two properties implicitly call other validation
        self._get_main_filter()
        self._get_deleted_filter()
        self.indicators
        self.parsed_expression


    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/data_sources_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda config: config.display_name
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.get_db().view('userreports/data_sources_by_domain',
                                                      reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)


class ReportConfiguration(UnicodeMixIn, CachedCouchDocumentMixin, Document):
    """
    A report configuration. These map 1:1 with reports that show up in the UI.
    """
    domain = StringProperty(required=True)
    visible = BooleanProperty(default=True)
    config_id = StringProperty(required=True)
    title = StringProperty()
    description = StringProperty()
    aggregation_columns = StringListProperty()
    filters = ListProperty()
    columns = ListProperty()
    configured_charts = ListProperty()

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.title)

    @property
    @memoized
    def config(self):
        try:
            return DataSourceConfiguration.get(self.config_id)
        except ResourceNotFound:
            raise BadSpecError(_('The data source referenced by this report could not be found.'))

    @property
    @memoized
    def ui_filters(self):
        return [ReportFilterFactory.from_spec(f) for f in self.filters]

    @property
    @memoized
    def charts(self):
        return [ChartFactory.from_spec(g._obj) for g in self.configured_charts]

    @property
    def table_id(self):
        return self.config.table_id

    def get_ui_filter(self, filter_slug):
        for filter in self.ui_filters:
            if filter.name == filter_slug:
                return filter
        return None

    def validate(self, required=True):
        def _check_for_duplicate_slugs(filters):
            slugs = [FilterSpec.wrap(f).slug for f in filters]
            # http://stackoverflow.com/questions/9835762/find-and-list-duplicates-in-python-list
            duplicated_slugs = set(
                [slug for slug in slugs if slugs.count(slug) > 1]
            )
            if len(duplicated_slugs) > 0:
                raise BadSpecError(
                    _('Filters cannot contain duplicate slugs: %s')
                    % ', '.join(sorted(duplicated_slugs))
                )

        super(ReportConfiguration, self).validate(required)

        # these calls implicitly do validation
        ReportFactory.from_spec(self)
        self.ui_filters
        self.charts

        _check_for_duplicate_slugs(self.filters)

    @classmethod
    def by_domain(cls, domain):
        return sorted(
            cls.view('userreports/report_configs_by_domain', key=domain, reduce=False, include_docs=True),
            key=lambda report: report.title,
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.view('userreports/report_configs_by_domain',
                                             reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)


class CustomDataSourceConfiguration(JsonObject):
    _datasource_id_prefix = 'custom-'
    domains = ListProperty()
    config = DictProperty()

    @classmethod
    def get_doc_id(cls, table_id):
        return '{}{}'.format(cls._datasource_id_prefix, table_id)

    @classmethod
    def all(cls):
        for path in settings.CUSTOM_DATA_SOURCES:
            with open(path) as f:
                wrapped = cls.wrap(json.load(f))
                for domain in wrapped.domains:
                    doc = copy(wrapped.config)
                    doc['domain'] = domain
                    doc['_id'] = cls.get_doc_id(doc['table_id'])
                    yield DataSourceConfiguration.wrap(doc)

    @classmethod
    def by_domain(cls, domain):
        return [ds for ds in cls.all() if ds.domain == domain]

    @classmethod
    def by_id(cls, config_id):
        matching = [ds for ds in cls.all() if ds.get_id == config_id]
        if not matching:
            return None
        return matching[0]
