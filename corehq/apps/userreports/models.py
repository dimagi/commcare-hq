from copy import copy
import json
from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    DocumentSchema,
    SchemaProperty,
    StringListProperty,
)
from dimagi.ext.couchdbkit import StringProperty, DictProperty, ListProperty, IntegerProperty
from dimagi.ext.jsonobject import JsonObject
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.userreports.dbaccessors import get_number_of_report_configs_by_data_source, \
    get_report_configs_for_domain, get_all_report_configs
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.indicators import CompoundIndicator
from corehq.apps.userreports.reports.factory import ReportFactory, ChartFactory, ReportFilterFactory, \
    ReportColumnFactory, ReportOrderByFactory
from corehq.apps.userreports.reports.specs import FilterSpec
from django.utils.translation import ugettext as _
from corehq.apps.userreports.specs import EvaluationContext
from corehq.pillows.utils import get_deleted_doc_types
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from django.conf import settings


class DataSourceBuildInformation(DocumentSchema):
    """
    A class to encapsulate meta information about the process through which
    its DataSourceConfiguration was configured and built.
    """
    # Either the case type or the form xmlns that this data source is based on.
    source_id = StringProperty()
    # The app that the form belongs to, or the app that was used to infer the case properties.
    app_id = StringProperty()
    # The version of the app at the time of the data source's configuration.
    app_version = IntegerProperty()
    # True if the data source has been built, that is, if the corresponding SQL table has been populated.
    finished = BooleanProperty(default=False)
    # Start time of the most recent build SQL table celery task.
    initiated = DateTimeProperty()


class DataSourceMeta(DocumentSchema):
    build = SchemaProperty(DataSourceBuildInformation)


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
    meta = SchemaProperty(DataSourceMeta)

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.display_name)

    def filter(self, document):
        filter_fn = self._get_main_filter()
        return filter_fn(document, EvaluationContext(document, 0))

    def deleted_filter(self, document):
        filter_fn = self._get_deleted_filter()
        return filter_fn and filter_fn(document, EvaluationContext(document, 0))

    @memoized
    def _get_main_filter(self):
        return self._get_filter([self.referenced_doc_type])

    @memoized
    def _get_deleted_filter(self):
        return self._get_filter(get_deleted_doc_types(self.referenced_doc_type))

    def _get_filter(self, doc_types):
        if not doc_types:
            return None

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
        default_indicators = [IndicatorFactory.from_spec({
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
        }, self.named_filter_objects)]

        default_indicators.append(IndicatorFactory.from_spec({
            "type": "inserted_at",
        }, self.named_filter_objects))

        if self.base_item_expression:
            default_indicators.append(IndicatorFactory.from_spec({
                "type": "repeat_iteration",
            }, self.named_filter_objects))
        return CompoundIndicator(
            self.display_name,
            default_indicators + [
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
        return [
            self.indicators.get_values(item, EvaluationContext(doc, i))
            for i, item in enumerate(self.get_items(doc))
        ]

    def get_report_count(self):
        """
        Return the number of ReportConfigurations that reference this data source.
        """
        return get_number_of_report_configs_by_data_source(self.domain, self._id)

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
            cls.view(
                'userreports/data_sources_by_build_info',
                start_key=[domain],
                end_key=[domain, {}],
                reduce=False,
                include_docs=True
            ),
            key=lambda config: config.display_name
        )

    @classmethod
    def all(cls):
        ids = [res['id'] for res in cls.get_db().view('userreports/data_sources_by_build_info',
                                                      reduce=False, include_docs=False)]
        for result in iter_docs(cls.get_db(), ids):
            yield cls.wrap(result)


class ReportMeta(DocumentSchema):
    # `True` if this report was initially constructed by the report builder.
    created_by_builder = BooleanProperty(default=False)
    builder_report_type = StringProperty(choices=['chart', 'list', 'table', 'worker'])


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
    sort_expression = ListProperty()
    report_meta = SchemaProperty(ReportMeta)

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
    def report_columns(self):
        return [ReportColumnFactory.from_spec(c) for c in self.columns]

    @property
    @memoized
    def ui_filters(self):
        return [ReportFilterFactory.from_spec(f) for f in self.filters]

    @property
    @memoized
    def charts(self):
        return [ChartFactory.from_spec(g._obj) for g in self.configured_charts]

    @property
    @memoized
    def sort_order(self):
        return [ReportOrderByFactory.from_spec(e) for e in self.sort_expression]

    @property
    def table_id(self):
        return self.config.table_id

    def get_ui_filter(self, filter_slug):
        for filter in self.ui_filters:
            if filter.name == filter_slug:
                return filter
        return None

    def get_languages(self):
        """
        Return the languages used in this report's column and filter display properties.
        Note that only explicitly identified languages are returned. So, if the
        display properties are all strings, "en" would not be returned.
        """
        langs = set()
        for item in self.columns + self.filters:
            if isinstance(item['display'], dict):
                langs |= set(item['display'].keys())
        return langs

    def validate(self, required=True):
        def _check_for_duplicates(supposedly_unique_list, error_msg):
            # http://stackoverflow.com/questions/9835762/find-and-list-duplicates-in-python-list
            duplicate_items = set(
                [item for item in supposedly_unique_list if supposedly_unique_list.count(item) > 1]
            )
            if len(duplicate_items) > 0:
                raise BadSpecError(
                    _(error_msg).format(', '.join(sorted(duplicate_items)))
                )

        super(ReportConfiguration, self).validate(required)

        # check duplicates before passing to factory since it chokes on them
        _check_for_duplicates(
            [FilterSpec.wrap(f).slug for f in self.filters],
            'Filters cannot contain duplicate slugs: {}',
        )
        _check_for_duplicates(
            [column_id for c in self.report_columns for column_id in c.get_column_ids()],
            'Columns cannot contain duplicate column_ids: {}',
        )

        # these calls all implicitly do validation
        ReportFactory.from_spec(self)
        self.ui_filters
        self.charts
        self.sort_order

    @classmethod
    def by_domain(cls, domain):
        return get_report_configs_for_domain(domain)

    @classmethod
    def all(cls):
        return get_all_report_configs()


CUSTOM_PREFIX = 'custom-'


class CustomDataSourceConfiguration(JsonObject):
    """
    For custom data sources maintained in the repository
    """
    _datasource_id_prefix = CUSTOM_PREFIX
    domains = ListProperty()
    config = DictProperty()

    @classmethod
    def get_doc_id(cls, domain, table_id):
        return '{}{}-{}'.format(cls._datasource_id_prefix, domain, table_id)

    @classmethod
    def all(cls):
        for path in settings.CUSTOM_DATA_SOURCES:
            with open(path) as f:
                wrapped = cls.wrap(json.load(f))
                for domain in wrapped.domains:
                    doc = copy(wrapped.config)
                    doc['domain'] = domain
                    doc['_id'] = cls.get_doc_id(domain, doc['table_id'])
                    yield DataSourceConfiguration.wrap(doc)

    @classmethod
    def by_domain(cls, domain):
        """
        Returns a list of DataSourceConfiguration objects,
        NOT CustomDataSourceConfigurations.
        """
        return [ds for ds in cls.all() if ds.domain == domain]

    @classmethod
    def by_id(cls, config_id):
        """
        Returns a DataSourceConfiguration object,
        NOT a CustomDataSourceConfiguration.
        """
        for ds in cls.all():
            if ds.get_id == config_id:
                return ds
        raise BadSpecError(_('The data source referenced by this report could '
                             'not be found.'))


class CustomReportConfiguration(JsonObject):
    """
    For statically defined reports based off of custom data sources
    """
    domains = ListProperty()
    report_id = StringProperty()
    data_source_table = StringProperty()
    config = DictProperty()

    @classmethod
    def get_doc_id(cls, domain, report_id):
        return '{}{}-{}'.format(CUSTOM_PREFIX, domain, report_id)

    @classmethod
    def all(cls):
        for path in settings.CUSTOM_UCR_REPORTS:
            with open(path) as f:
                wrapped = cls.wrap(json.load(f))
                for domain in wrapped.domains:
                    doc = copy(wrapped.config)
                    doc['domain'] = domain
                    doc['_id'] = cls.get_doc_id(domain, wrapped.report_id)
                    doc['config_id'] = CustomDataSourceConfiguration.get_doc_id(domain, wrapped.data_source_table)
                    yield ReportConfiguration.wrap(doc)

    @classmethod
    def by_domain(cls, domain):
        """
        Returns a list of ReportConfiguration objects, NOT CustomReportConfigurations.
        """
        return [ds for ds in cls.all() if ds.domain == domain]

    @classmethod
    def by_id(cls, config_id):
        """
        Returns a ReportConfiguration object, NOT CustomReportConfigurations.
        """
        for ds in cls.all():
            if ds.get_id == config_id:
                return ds
        raise BadSpecError(_('The report configuration referenced by this report could '
                             'not be found.'))
