from collections import namedtuple
from copy import copy, deepcopy
import json
from datetime import datetime

from corehq.sql_db.connections import UCR_ENGINE_ID
from corehq.util.quickcache import quickcache, skippable_quickcache
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
from corehq.apps.cachehq.mixins import (
    CachedCouchDocumentMixin,
    QuickCachedDocumentMixin,
)
from corehq.apps.userreports.const import UCR_SQL_BACKEND
from corehq.apps.userreports.dbaccessors import get_number_of_report_configs_by_data_source, \
    get_report_configs_for_domain, get_datasources_for_domain
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    ReportConfigurationNotFoundError,
    StaticDataSourceConfigurationNotFoundError,
)
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.indicators import CompoundIndicator
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.apps.userreports.reports.factory import ReportFactory, ChartFactory, \
    ReportColumnFactory, ReportOrderByFactory
from corehq.apps.userreports.reports.filters.specs import FilterSpec
from django.utils.translation import ugettext as _
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.utils import get_deleted_doc_types
from corehq.util.couch import get_document_or_not_found, DocumentNotFound
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from django.conf import settings

from dimagi.utils.modules import to_function


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
    engine_id = StringProperty(default=UCR_ENGINE_ID)
    backend_id = StringProperty(default=UCR_SQL_BACKEND)
    referenced_doc_type = StringProperty(required=True)
    table_id = StringProperty(required=True)
    display_name = StringProperty()
    base_item_expression = DictProperty()
    configured_filter = DictProperty()
    configured_indicators = ListProperty()
    named_expressions = DictProperty()
    named_filters = DictProperty()
    meta = SchemaProperty(DataSourceMeta)
    is_deactivated = BooleanProperty(default=False)
    last_modified = DateTimeProperty()

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def __unicode__(self):
        return u'{} - {}'.format(self.domain, self.display_name)

    def save(self, **params):
        self.last_modified = datetime.utcnow()
        super(DataSourceConfiguration, self).save(**params)

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
        return self._get_filter(get_deleted_doc_types(self.referenced_doc_type), include_configured=False)

    def _get_filter(self, doc_types, include_configured=True):
        if not doc_types:
            return None

        extras = (
            [self.configured_filter]
            if include_configured and self.configured_filter else []
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
            context=self._get_factory_context(),
        )

    def _get_domain_filter_spec(self):
        return {
            'type': 'property_match',
            'property_name': 'domain',
            'property_value': self.domain,
        }

    @property
    @memoized
    def named_expression_objects(self):
        named_expression_specs = deepcopy(self.named_expressions)
        named_expressions = {}
        spec_error = None
        while named_expression_specs:
            number_generated = 0
            for name, expression in named_expression_specs.items():
                try:
                    named_expressions[name] = ExpressionFactory.from_spec(
                        expression,
                        FactoryContext(named_expressions=named_expressions, named_filters={})
                    )
                    number_generated += 1
                    del named_expression_specs[name]
                except BadSpecError as spec_error:
                    # maybe a nested name resolution issue, try again on the next pass
                    pass
            if number_generated == 0 and named_expression_specs:
                # we unsuccessfully generated anything on this pass and there are still unresolved
                # references. we have to fail.
                assert spec_error is not None
                raise spec_error
        return named_expressions

    @property
    @memoized
    def named_filter_objects(self):
        return {name: FilterFactory.from_spec(filter, FactoryContext(self.named_expression_objects, {}))
                for name, filter in self.named_filters.items()}

    def _get_factory_context(self):
        return FactoryContext(self.named_expression_objects, self.named_filter_objects)

    @property
    @memoized
    def default_indicators(self):
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
        }, self._get_factory_context())]

        default_indicators.append(IndicatorFactory.from_spec({
            "type": "inserted_at",
        }, self._get_factory_context()))

        if self.base_item_expression:
            default_indicators.append(IndicatorFactory.from_spec({
                "type": "repeat_iteration",
            }, self._get_factory_context()))

        return default_indicators

    @property
    @memoized
    def indicators(self):

        return CompoundIndicator(
            self.display_name,
            self.default_indicators + [
                IndicatorFactory.from_spec(indicator, self._get_factory_context())
                for indicator in self.configured_indicators
            ]
        )

    @property
    @memoized
    def parsed_expression(self):
        if self.base_item_expression:
            return ExpressionFactory.from_spec(self.base_item_expression, context=self._get_factory_context())
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
        return ReportConfiguration.count_by_data_source(self.domain, self._id)

    def validate(self, required=True):
        super(DataSourceConfiguration, self).validate(required)
        # these two properties implicitly call other validation
        self._get_main_filter()
        self._get_deleted_filter()

        # validate indicators and column uniqueness
        columns = [c.id for c in self.indicators.get_columns()]
        unique_columns = set(columns)
        if len(columns) != len(unique_columns):
            for column in set(columns):
                columns.remove(column)
            raise BadSpecError(_('Report contains duplicate column ids: {}').format(', '.join(set(columns))))

        self.parsed_expression

    @classmethod
    def by_domain(cls, domain):
        return get_datasources_for_domain(domain)

    @classmethod
    def all_ids(cls):
        return [res['id'] for res in cls.get_db().view('userreports/data_sources_by_build_info',
                                                       reduce=False, include_docs=False)]

    @classmethod
    def all(cls):
        for result in iter_docs(cls.get_db(), cls.all_ids()):
            yield cls.wrap(result)

    @property
    def is_static(self):
        return id_is_static(self._id)

    def deactivate(self):
        if not self.is_static:
            self.is_deactivated = True
            self.save()
            get_indicator_adapter(self).drop_table()


class ReportMeta(DocumentSchema):
    # `True` if this report was initially constructed by the report builder.
    created_by_builder = BooleanProperty(default=False)
    # `True` if this report was ever edited in the advanced JSON UIs (after June 7, 2016)
    edited_manually = BooleanProperty(default=False)
    last_modified = DateTimeProperty()
    builder_report_type = StringProperty(choices=['chart', 'list', 'table', 'worker', 'map'])


class ReportConfiguration(UnicodeMixIn, QuickCachedDocumentMixin, Document):
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

    def save(self, *args, **kwargs):
        self.report_meta.last_modified = datetime.utcnow()
        super(ReportConfiguration, self).save(*args, **kwargs)

    @property
    @memoized
    def filters_without_prefilters(self):
        return [f for f in self.filters if f['type'] != 'pre']

    @property
    @memoized
    def prefilters(self):
        return [f for f in self.filters if f['type'] == 'pre']

    @property
    @memoized
    def config(self):
        return get_datasource_config(self.config_id, self.domain)[0]

    @property
    @memoized
    def report_columns(self):
        return [ReportColumnFactory.from_spec(c) for c in self.columns]

    @property
    @memoized
    def ui_filters(self):
        return [ReportFilterFactory.from_spec(f, self) for f in self.filters]

    @property
    @memoized
    def charts(self):
        return [ChartFactory.from_spec(g._obj) for g in self.configured_charts]

    @property
    @memoized
    def location_column_id(self):
        cols = [col for col in self.report_columns if col.type == 'location']
        if cols:
            return cols[0].column_id

    @property
    def map_config(self):
        def map_col(column):
            if column['column_id'] != self.location_column_id:
                return {
                    'column_id': column['column_id'],
                    'label': column['display']
                }

        if self.location_column_id:
            return {
                'location_column_id': self.location_column_id,
                'layer_name': {
                    'XFormInstance': _('Forms'),
                    'CommCareCase': _('Cases')
                }.get(self.config.referenced_doc_type, "Layer"),
                'columns': filter(None, [map_col(col) for col in self.columns])
            }

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
    @quickcache(['cls.__name__', 'domain'])
    def by_domain(cls, domain):
        return get_report_configs_for_domain(domain)

    @classmethod
    @quickcache(['cls.__name__', 'domain', 'data_source_id'])
    def count_by_data_source(cls, domain, data_source_id):
        return get_number_of_report_configs_by_data_source(domain, data_source_id)

    def clear_caches(self):
        super(ReportConfiguration, self).clear_caches()
        self.by_domain.clear(self.__class__, self.domain)
        self.count_by_data_source.clear(self.__class__, self.domain, self.config_id)

    @property
    def is_static(self):
        return report_config_id_is_static(self._id)

STATIC_PREFIX = 'static-'
CUSTOM_REPORT_PREFIX = 'custom-'

StaticDataSourceMetadata = namedtuple('StaticDataSourceMetadata', 'id path domain')
StaticReportMetadata = namedtuple('StaticReportMetadata', 'id path domain')


class StaticDataSourceConfiguration(JsonObject):
    """
    For custom data sources maintained in the repository
    """
    _datasource_id_prefix = STATIC_PREFIX
    domains = ListProperty()
    config = DictProperty()

    @classmethod
    def get_doc_id(cls, domain, table_id):
        return '{}{}-{}'.format(cls._datasource_id_prefix, domain, table_id)

    @classmethod
    @skippable_quickcache([], skip_arg='rebuild')
    def by_id_mapping(cls, rebuild=False):
        mapping = {}
        for wrapped, path in cls._all():
            for domain in wrapped.domains:
                ds_id = cls.get_doc_id(domain, wrapped.config['table_id'])
                mapping[ds_id] = StaticDataSourceMetadata(ds_id, path, domain)
        return mapping

    @classmethod
    def _all(cls):
        for path in settings.STATIC_DATA_SOURCES:
            with open(path) as f:
                yield cls.wrap(json.load(f)), path

        for provider_path in settings.STATIC_DATA_SOURCE_PROVIDERS:
            provider_fn = to_function(provider_path, failhard=True)
            for wrapped, path in provider_fn():
                yield wrapped, path

    @classmethod
    def all(cls):
        for wrapped, path in cls._all():
            for domain in wrapped.domains:
                yield cls._get_datasource_config(wrapped, domain)

    @classmethod
    def by_domain(cls, domain):
        """
        Returns a list of DataSourceConfiguration objects,
        NOT StaticDataSourceConfigurations.
        """
        return [ds for ds in cls.all() if ds.domain == domain]

    @classmethod
    def by_id(cls, config_id):
        """
        Returns a DataSourceConfiguration object,
        NOT a StaticDataSourceConfiguration.
        """
        mapping = cls.by_id_mapping()
        if config_id not in mapping:
            mapping = cls.by_id_mapping(rebuild=True)

        metadata = mapping.get(config_id, None)
        if not metadata:
            raise StaticDataSourceConfigurationNotFoundError(_(
                'The data source referenced by this report could not be found.'
            ))

        return cls._get_from_metadata(metadata)

    @classmethod
    def _get_from_metadata(cls, metadata):
        with open(metadata.path) as f:
            wrapped = cls.wrap(json.load(f))
            return cls._get_datasource_config(wrapped, metadata.domain)

    @classmethod
    def _get_datasource_config(cls, static_config, domain):
        doc = deepcopy(static_config.to_json()['config'])
        doc['domain'] = domain
        doc['_id'] = cls.get_doc_id(domain, doc['table_id'])
        return DataSourceConfiguration.wrap(doc)


class StaticReportConfiguration(JsonObject):
    """
    For statically defined reports based off of custom data sources
    """
    domains = ListProperty()
    report_id = StringProperty()
    data_source_table = StringProperty()
    config = DictProperty()
    custom_configurable_report = StringProperty()

    @classmethod
    def get_doc_id(cls, domain, report_id, custom_configurable_report):
        return '{}{}-{}'.format(
            STATIC_PREFIX if not custom_configurable_report else CUSTOM_REPORT_PREFIX,
            domain,
            report_id,
        )

    @classmethod
    def _all(cls):
        for path in settings.STATIC_UCR_REPORTS:
            with open(path) as f:
                yield cls.wrap(json.load(f)), path

    @classmethod
    @skippable_quickcache([], skip_arg='rebuild')
    def by_id_mapping(cls, rebuild=False):
        mapping = {}
        for wrapped, path in StaticReportConfiguration._all():
            for domain in wrapped.domains:
                config_id = cls.get_doc_id(domain, wrapped.report_id, wrapped.custom_configurable_report)
                mapping[config_id] = StaticReportMetadata(config_id, path, domain)
        return mapping

    @classmethod
    def all(cls):
        for wrapped, path in StaticReportConfiguration._all():
            for domain in wrapped.domains:
                yield cls._get_report_config(wrapped, domain)

    @classmethod
    def by_domain(cls, domain):
        """
        Returns a list of ReportConfiguration objects, NOT StaticReportConfigurations.
        """
        return [ds for ds in cls.all() if ds.domain == domain]

    @classmethod
    def by_id(cls, config_id, domain=None):
        """
        Returns a ReportConfiguration object, NOT StaticReportConfigurations.

        :param domain: Optionally specify domain name to validate access.
                       Raises ``DocumentNotFound`` if domains don't match.
        """
        mapping = cls.by_id_mapping()
        if config_id not in mapping:
            mapping = cls.by_id_mapping(rebuild=True)

        metadata = mapping.get(config_id, None)
        if not metadata:
            raise BadSpecError(_('The report configuration referenced by this report could '
                                 'not be found.'))

        config = cls._get_from_metadata(metadata)
        if domain and config.domain != domain:
            raise DocumentNotFound("Document {} of class {} not in domain {}!".format(
                config_id,
                config.__class__.__name__,
                domain,
            ))
        return config

    @classmethod
    def by_ids(cls, config_ids):
        config_ids = set(config_ids)
        mapping = cls.by_id_mapping()

        if not config_ids <= set(mapping.keys()):
            mapping = cls.by_id_mapping(rebuild=True)

        return_configs = []
        for config_id in config_ids:
            metadata = mapping.get(config_id, None)
            if not metadata:
                raise ReportConfigurationNotFoundError(_(
                    "The following report configuration could not be found: {}".format(config_id)
                ))
            return_configs.append(cls._get_from_metadata(metadata))
        return return_configs

    @classmethod
    def report_class_by_domain_and_id(cls, domain, config_id):
        for wrapped, path in cls._all():
            if cls.get_doc_id(domain, wrapped.report_id, wrapped.custom_configurable_report) == config_id:
                return wrapped.custom_configurable_report
        raise BadSpecError(_('The report configuration referenced by this report could '
                             'not be found.'))

    @classmethod
    def _get_from_metadata(cls, metadata):
        with open(metadata.path) as f:
            wrapped = cls.wrap(json.load(f))
            domain = metadata.domain
            return cls._get_report_config(wrapped, domain)

    @classmethod
    def _get_report_config(cls, static_config, domain):
        doc = copy(static_config.to_json()['config'])
        doc['domain'] = domain
        doc['_id'] = cls.get_doc_id(domain, static_config.report_id, static_config.custom_configurable_report)
        doc['config_id'] = StaticDataSourceConfiguration.get_doc_id(domain, static_config.data_source_table)
        return ReportConfiguration.wrap(doc)


def get_datasource_config(config_id, domain):
    def _raise_not_found():
        raise DataSourceConfigurationNotFoundError(_(
            'The data source referenced by this report could not be found.'
        ))

    is_static = id_is_static(config_id)
    if is_static:
        config = StaticDataSourceConfiguration.by_id(config_id)
        if config.domain != domain:
            _raise_not_found()
    else:
        try:
            config = get_document_or_not_found(DataSourceConfiguration, domain, config_id)
        except DocumentNotFound:
            _raise_not_found()
    return config, is_static


def id_is_static(data_source_id):
    if data_source_id is None:
        return False
    return data_source_id.startswith(StaticDataSourceConfiguration._datasource_id_prefix)


def report_config_id_is_static(config_id):
    """
    Return True if the given report configuration id refers to a static report
    configuration.
    """
    return any(
        config_id.startswith(prefix)
        for prefix in [STATIC_PREFIX, CUSTOM_REPORT_PREFIX]
    )


def get_report_configs(config_ids, domain):
    """
    Return a list of ReportConfigurations.
    config_ids may be ReportConfiguration or StaticReportConfiguration ids.
    """

    static_report_config_ids = []
    dynamic_report_config_ids = []
    for config_id in config_ids:
        if report_config_id_is_static(config_id):
            static_report_config_ids.append(config_id)
        else:
            dynamic_report_config_ids.append(config_id)
    static_report_configs = StaticReportConfiguration.by_ids(static_report_config_ids)
    for config in static_report_configs:
        if config.domain != domain:
            raise ReportConfigurationNotFoundError

    dynamic_report_configs = [
        ReportConfiguration.wrap(doc) for doc in
        get_docs(ReportConfiguration.get_db(), dynamic_report_config_ids)
    ]
    if len(dynamic_report_configs) != len(dynamic_report_config_ids):
        raise ReportConfigurationNotFoundError
    for config in dynamic_report_configs:
        if config.domain != domain:
            raise ReportConfigurationNotFoundError

    return dynamic_report_configs + static_report_configs


def get_report_config(config_id, domain):
    """
    Return a ReportConfiguration, and if it is static or not.
    config_id may be a ReportConfiguration or StaticReportConfiguration id
    """
    config = get_report_configs([config_id], domain)[0]
    return config, report_config_id_is_static(config_id)
