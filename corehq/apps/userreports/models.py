import glob
import json
import os
import re
from ast import literal_eval
from collections import namedtuple
from copy import copy, deepcopy
from datetime import datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

import requests
import yaml
from celery.states import FAILURE
from couchdbkit.exceptions import BadValueError
from django_bulk_update.helper import bulk_update as bulk_update_helper
from jsonpath_ng.ext import parser
from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DecimalProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.ext.jsonobject import JsonObject
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import is_deleted
from dimagi.utils.dates import DateSpan
from dimagi.utils.modules import to_function

from corehq import toggles
from corehq.apps.cachehq.mixins import (
    CachedCouchDocumentMixin,
    QuickCachedDocumentMixin,
)
from corehq.apps.domain.models import AllowedUCRExpressionSettings
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.userreports.app_manager.data_source_meta import (
    REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES,
)
from corehq.apps.userreports.columns import get_expanded_column_config
from corehq.apps.userreports.const import (
    ALL_EXPRESSION_TYPES,
    DATA_SOURCE_TYPE_AGGREGATE,
    DATA_SOURCE_TYPE_STANDARD,
    FILTER_INTERPOLATION_DOC_TYPES,
    UCR_NAMED_EXPRESSION,
    UCR_NAMED_FILTER,
    UCR_SQL_BACKEND,
    VALID_REFERENCED_DOC_TYPES,
)
from corehq.apps.userreports.dbaccessors import (
    get_all_registry_data_source_ids,
    get_datasources_for_domain,
    get_number_of_registry_report_configs_by_data_source,
    get_number_of_report_configs_by_data_source,
    get_registry_data_sources_by_domain,
    get_registry_report_configs_for_domain,
    get_report_configs_for_domain,
)
from corehq.apps.userreports.exceptions import (
    BadSpecError,
    DataSourceConfigurationNotFoundError,
    DuplicateColumnIdError,
    InvalidDataSourceType,
    ReportConfigurationNotFoundError,
    StaticDataSourceConfigurationNotFoundError,
    ValidationError,
)
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.extension_points import (
    static_ucr_data_source_paths,
    static_ucr_report_paths,
)
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.indicators import CompoundIndicator
from corehq.apps.userreports.indicators.factory import IndicatorFactory
from corehq.apps.userreports.reports.factory import (
    ChartFactory,
    ReportColumnFactory,
    ReportOrderByFactory,
)
from corehq.apps.userreports.reports.filters.factory import ReportFilterFactory
from corehq.apps.userreports.reports.filters.specs import FilterSpec
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.apps.userreports.sql.util import decode_column_name
from corehq.apps.userreports.util import (
    get_async_indicator_modify_lock_key,
    get_indicator_adapter,
    wrap_report_config_by_type,
)
from corehq.pillows.utils import get_deleted_doc_types
from corehq.sql_db.connections import UCR_ENGINE_ID, connection_manager
from corehq.util.couch import DocumentNotFound, get_document_or_not_found
from corehq.util.quickcache import quickcache

ID_REGEX_CHECK = re.compile(r"^[\w\-:]+$")


def _check_ids(value):
    if not ID_REGEX_CHECK.match(value):
        raise BadValueError("Invalid ID: '{}'".format(value))


class DataSourceActionLog(models.Model):
    """
    Audit model that tracks changes to UCRs and their underlying tables.
    """
    BUILD = 'build'
    MIGRATE = 'migrate'
    REBUILD = 'rebuild'
    DROP = 'drop'

    domain = models.CharField(max_length=126, null=False, db_index=True)
    indicator_config_id = models.CharField(max_length=126, null=False, db_index=True)
    initiated_by = models.CharField(max_length=126, null=True, blank=True)
    action_source = models.CharField(max_length=126, null=True, db_index=True)
    date_created = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=(
        (BUILD, _('Build')),
        (MIGRATE, _('Migrate')),
        (REBUILD, _('Rebuild')),
        (DROP, _('Drop')),
    ), db_index=True, null=False)
    migration_diffs = models.JSONField(null=True, blank=True)

    # True for actions that were skipped because the data source
    # was marked with ``disable_destructive_rebuild``
    skip_destructive = models.BooleanField(default=False)


class SQLColumnIndexes(DocumentSchema):
    column_ids = StringListProperty()


class SQLPartition(DocumentSchema):
    """Uses architect library to partition

    http://architect.readthedocs.io/features/partition/index.html
    """
    column = StringProperty()
    subtype = StringProperty(choices=['date', 'string_firstchars', 'string_lastchars'])
    constraint = StringProperty()


class SQLSettings(DocumentSchema):
    partition_config = SchemaListProperty(SQLPartition)  # no longer used
    primary_key = ListProperty()


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
    # The registry_slug associated with the registry of the report.
    registry_slug = StringProperty()
    # True if the data source has been built, that is, if the corresponding SQL table has been populated.
    finished = BooleanProperty(default=False)
    # Start time of the most recent build SQL table celery task.
    initiated = DateTimeProperty()
    # same as previous attributes but used for rebuilding tables in place
    finished_in_place = BooleanProperty(default=False)
    initiated_in_place = DateTimeProperty()
    rebuilt_asynchronously = BooleanProperty(default=False)

    @property
    def is_rebuilding(self):
        return (
            self.initiated
            and not self.finished
            and not self.rebuilt_asynchronously
        )

    @property
    def is_rebuilding_in_place(self):
        return (
            self.initiated_in_place
            and not self.finished_in_place
        )

    @property
    def is_rebuild_in_progress(self):
        return self.is_rebuilding or self.is_rebuilding_in_place

    def rebuild_failed(self, data_source_config_id):
        """
        Returns ``True`` if the rebuild failed, ``False`` if it succeeded
        or has not yet failed, or ``None`` if Flower is not available.
        """
        flower_url = getattr(settings, 'CELERY_FLOWER_URL', None)

        def none_max(a, b):
            if a is None:
                return b
            if b is None:
                return a
            return max(a, b)

        def format_datetime(dt):
            return dt.strftime('%Y-%m-%d %H:%M')

        def is_this_data_source(rebuild_task):
            args = literal_eval(rebuild_task['args'])  # a tuple
            return args[0] == data_source_config_id

        def iter_tasks():
            task_names = (
                'corehq.apps.userreports.tasks.rebuild_indicators',
                'corehq.apps.userreports.tasks.rebuild_indicators_in_place',
                'corehq.apps.userreports.tasks.resume_building_indicators',
            )
            initiated_at = none_max(self.initiated, self.initiated_in_place)
            start = format_datetime(initiated_at - timedelta(seconds=60))
            for task_name in task_names:
                tasks = requests.get(
                    flower_url + '/api/tasks',
                    params={
                        'taskname': task_name,
                        'received_start': start,
                    },
                    timeout=3,
                ).json()
                for task_uuid, task in tasks.items():
                    if is_this_data_source(task):
                        yield task

        if not self.initiated and not self.initiated_in_place:
            # The rebuild task hasn't started.
            return False

        if (
            (self.initiated and self.finished)
            or (self.initiated_in_place and self.finished_in_place)
        ):
            # The rebuild task completed.
            return False

        if not flower_url:
            # We are unable to find out about the rebuild task.
            return None

        rebuild_tasks = sorted(iter_tasks(), key=lambda t: t['started'])
        if rebuild_tasks:
            # Return True if the last task failed, otherwise return False.
            return rebuild_tasks[-1]['state'] == FAILURE

        # The rebuild is not finished and the task is not found. It must
        # have died.
        return True


class DataSourceMeta(DocumentSchema):
    build = SchemaProperty(DataSourceBuildInformation)

    # If this is a linked datasource, this is the ID of the datasource this pulls from
    master_id = StringProperty()


class Validation(DocumentSchema):
    name = StringProperty(required=True)
    expression = DictProperty(required=True)
    error_message = StringProperty(required=True)


class AbstractUCRDataSource(object):
    """
    Base wrapper class for datasource-like things to be used in reports.

    This doesn't use abc because of this issue: https://stackoverflow.com/q/8723639/8207

    This is not really a "designed" interface so much as the set of methods/properties that
    the objects need to have in order to work with UCRs.

    In addition to the methods defined, the following should also exist:

    domain: a string
    engine_id: a string
    table_id: a string
    display_name: a string
    sql_column_indexes: a list of SQLColumnIndexes
    sql_settings: a SQLSettings object
    """
    @property
    def data_source_id(self):
        """
        The data source's ID
        """
        raise NotImplementedError()

    def get_columns(self):
        raise NotImplementedError()

    @property
    def pk_columns(self):
        raise NotImplementedError()


class MirroredEngineIds(DocumentSchema):
    server_environment = StringProperty()
    engine_ids = StringListProperty()


class DataSourceConfiguration(CachedCouchDocumentMixin, Document, AbstractUCRDataSource):
    """
    A data source configuration. These map 1:1 with database tables that get created.
    Each data source can back an arbitrary number of reports.
    """
    domain = StringProperty(required=True)
    engine_id = StringProperty(default=UCR_ENGINE_ID)
    backend_id = StringProperty(default=UCR_SQL_BACKEND)  # no longer used
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
    asynchronous = BooleanProperty(default=False)
    is_available_in_analytics = BooleanProperty(default=False)
    sql_column_indexes = SchemaListProperty(SQLColumnIndexes)
    disable_destructive_rebuild = BooleanProperty(default=False)
    sql_settings = SchemaProperty(SQLSettings)
    validations = SchemaListProperty(Validation)
    mirrored_engine_ids = ListProperty(default=[])

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def __str__(self):
        return '{} - {}'.format(self.domain, self.display_name)

    @property
    def is_deleted(self):
        return is_deleted(self)

    def save(self, **params):
        self.last_modified = datetime.utcnow()
        super(DataSourceConfiguration, self).save(**params)

    @property
    def data_source_id(self):
        return self._id

    def filter(self, document, eval_context=None):
        if eval_context is None:
            eval_context = EvaluationContext(document)

        filter_fn = self._get_main_filter()
        return filter_fn(document, eval_context)

    def deleted_filter(self, document):
        filter_fn = self._get_deleted_filter()
        return filter_fn and filter_fn(document, EvaluationContext(document, 0))

    @property
    def has_validations(self):
        return len(self.validations) > 0

    def validate_document(self, document, eval_context=None):
        if eval_context is None:
            eval_context = EvaluationContext(document)

        errors = []
        for validation in self._validations():
            if validation.validation_function(document, eval_context) is False:
                errors.append((validation.name, validation.error_message))

        if errors:
            raise ValidationError(errors)

    @memoized
    def _validations(self):
        return [
            _Validation(
                validation.name,
                validation.error_message,
                FilterFactory.from_spec(validation.expression, self.get_factory_context())
            )
            for validation in self.validations
        ]

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
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_name",
                            "property_name": "doc_type",
                        },
                        "operator": "eq",
                        "property_value": doc_type,
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
            self.get_factory_context(),
        )

    def _get_domain_filter_spec(self):
        return {
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "domain",
            },
            "operator": "eq",
            "property_value": self.domain,
        }

    @property
    @memoized
    def named_expression_objects(self):
        named_expression_specs = deepcopy(self.named_expressions)
        named_expressions = {}
        spec_error = None
        factory_context = FactoryContext(named_expressions=named_expressions, named_filters={}, domain=self.domain)
        while named_expression_specs:
            number_generated = 0
            for name, expression in list(named_expression_specs.items()):
                try:
                    factory_context.named_expressions = named_expressions
                    named_expressions[name] = ExpressionFactory.from_spec(expression, factory_context)
                    number_generated += 1
                    del named_expression_specs[name]
                except BadSpecError as bad_spec_error:
                    # maybe a nested name resolution issue, try again on the next pass
                    spec_error = bad_spec_error
            if number_generated == 0 and named_expression_specs:
                # we unsuccessfully generated anything on this pass and there are still unresolved
                # references. we have to fail.
                assert spec_error is not None
                raise spec_error
        return named_expressions

    @property
    @memoized
    def named_filter_objects(self):
        factory_context = FactoryContext(self.named_expression_objects, {}, domain=self.domain)
        return {
            name: FilterFactory.from_spec(filter, factory_context)
            for name, filter in self.named_filters.items()
        }

    def get_factory_context(self):
        return FactoryContext(self.named_expression_objects, self.named_filter_objects, self.domain)

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
        }, self.get_factory_context())]

        default_indicators.append(self._get_inserted_at_indicator())

        if self.base_item_expression:
            default_indicators.append(IndicatorFactory.from_spec({
                "type": "repeat_iteration",
            }, self.get_factory_context()))

        return default_indicators

    def _get_inserted_at_indicator(self):
        return IndicatorFactory.from_spec({
            "type": "inserted_at",
        }, self.get_factory_context())

    @property
    @memoized
    def indicators(self):
        return CompoundIndicator(
            self.display_name,
            self.default_indicators + [
                IndicatorFactory.from_spec(indicator, self.get_factory_context())
                for indicator in self.configured_indicators
            ],
            None,
        )

    @property
    @memoized
    def parsed_expression(self):
        if self.base_item_expression:
            return ExpressionFactory.from_spec(self.base_item_expression, self.get_factory_context())
        return None

    @memoized
    def get_columns(self):
        return self.indicators.get_columns()

    @property
    @memoized
    def columns_by_id(self):
        return {c.id: c for c in self.get_columns()}

    def get_column_by_id(self, column_id):
        return self.columns_by_id.get(column_id)

    def get_items(self, document, eval_context=None):
        if self.filter(document, eval_context):
            if not self.base_item_expression:
                return [document]
            else:
                result = self.parsed_expression(document, eval_context)
                if result is None:
                    return []
                elif isinstance(result, list):
                    return result
                else:
                    return [result]
        else:
            return []

    def get_all_values(self, doc, eval_context=None):
        if not eval_context:
            eval_context = EvaluationContext(doc)

        if self.has_validations:
            try:
                self.validate_document(doc, eval_context)
            except ValidationError as e:
                for error in e.errors:
                    InvalidUCRData.objects.get_or_create(
                        doc_id=doc['_id'],
                        indicator_config_id=self._id,
                        validation_name=error[0],
                        defaults={
                            'doc_type': doc['doc_type'],
                            'domain': doc['domain'],
                            'validation_text': error[1],
                        }
                    )
                return []

        rows = []
        for item in self.get_items(doc, eval_context):
            values = self.indicators.get_values(item, eval_context)
            rows.append(values)
            eval_context.increment_iteration()

        return rows

    def get_report_count(self):
        """
        Return the number of ReportConfigurations that reference this data source.
        """
        return ReportConfiguration.count_by_data_source(self.domain, self._id)

    def validate_db_config(self):
        mirrored_engine_ids = self.mirrored_engine_ids
        if not mirrored_engine_ids:
            return
        if self.engine_id in mirrored_engine_ids:
            raise BadSpecError("mirrored_engine_ids list should not contain engine_id")

        for engine_id in mirrored_engine_ids:
            if not connection_manager.engine_id_is_available(engine_id):
                raise BadSpecError(
                    "DB for engine_id {} is not availble".format(engine_id)
                )

        if not connection_manager.resolves_to_unique_dbs(mirrored_engine_ids + [self.engine_id]):
            raise BadSpecError("No two engine_ids should point to the same database")

    @property
    def data_domains(self):
        return [self.domain]

    def _verify_contains_allowed_expressions(self):
        """
        Raise BadSpecError if any disallowed expression is present in datasource
        """
        disallowed_expressions = AllowedUCRExpressionSettings.disallowed_ucr_expressions(self.domain)
        if 'base_item_expression' in disallowed_expressions and self.base_item_expression:
            raise BadSpecError(_(f'base_item_expression is not allowed for domain {self.domain}'))
        doubtful_keys = dict(indicators=self.configured_indicators, expressions=self.named_expressions)
        for expr in disallowed_expressions:
            results = parser.parse(f"$..[*][?type={expr}]").find(doubtful_keys)
            if results:
                raise BadSpecError(_(f'{expr} is not allowed for domain {self.domain}'))

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
            raise DuplicateColumnIdError(columns=columns)

        if self.referenced_doc_type not in VALID_REFERENCED_DOC_TYPES:
            raise BadSpecError(
                _('Report contains invalid referenced_doc_type: {}').format(self.referenced_doc_type))
        self._verify_contains_allowed_expressions()
        self.parsed_expression
        self.pk_columns

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

    def deactivate(self, initiated_by=None):
        if not self.is_static:
            self.is_deactivated = True
            self.save()
            get_indicator_adapter(self).drop_table(initiated_by=initiated_by, source='deactivate-data-source')

    def get_case_type_or_xmlns_filter(self):
        """Returns a list of case types or xmlns from the filter of this data source.

        If this can't figure out the case types or xmlns's that filter, then returns [None]
        Currently always returns a list because it is called by a loop in _iteratively_build_table
        Could be reworked to return [] to be more pythonic
        """
        if self.referenced_doc_type not in FILTER_INTERPOLATION_DOC_TYPES:
            return [None]

        property_name = FILTER_INTERPOLATION_DOC_TYPES[self.referenced_doc_type]
        prop_value = self._filter_interploation_helper(self.configured_filter, property_name)

        return prop_value or [None]

    def _filter_interploation_helper(self, config_filter, property_name):
        filter_type = config_filter.get('type')
        if filter_type == 'and':
            sub_config_filters = [
                self._filter_interploation_helper(f, property_name)
                for f in config_filter.get('filters')
            ]
            for filter_ in sub_config_filters:
                if filter_[0]:
                    return filter_

        if filter_type != 'boolean_expression':
            return [None]

        if config_filter['operator'] not in ('eq', 'in'):
            return [None]

        expression = config_filter['expression']

        if not isinstance(expression, dict):
            return [None]

        if expression['type'] == 'property_name' and expression['property_name'] == property_name:
            prop_value = config_filter['property_value']
            if not isinstance(prop_value, list):
                prop_value = [prop_value]
            return prop_value
        return [None]

    @property
    def pk_columns(self):
        columns = []
        for col in self.get_columns():
            if col.is_primary_key:
                column_name = decode_column_name(col)
                columns.append(column_name)
        if self.sql_settings.primary_key:
            if set(columns) != set(self.sql_settings.primary_key):
                raise BadSpecError("Primary key columns must have is_primary_key set to true", self.data_source_id)
            columns = self.sql_settings.primary_key
        return columns

    @cached_property
    def rebuild_failed(self):
        # `has_died()` returns `None` if we can't use the Flower API,
        # and so we don't know. Treating `None` as falsy allows calling
        # code to give `rebuild_has_died` the benefit of the doubt.
        return self.meta.build.rebuild_failed(self._id)


class RegistryDataSourceConfiguration(DataSourceConfiguration):
    """This is a special data source that can contain data from
    multiple domains. These data sources are built from
    data accessible to the domain via a Data Registry."""

    # this field indicates whether the data source is available
    # to all domains participating in the registry
    globally_accessible = BooleanProperty(default=False)
    registry_slug = StringProperty(required=True)

    @cached_property
    def registry_helper(self):
        return DataRegistryHelper(self.domain, registry_slug=self.registry_slug)

    @property
    def data_domains(self):
        if self.globally_accessible:
            return self.registry_helper.participating_domains
        else:
            return self.registry_helper.visible_domains

    def validate(self, required=True):
        super().validate(required)
        if self.referenced_doc_type != 'CommCareCase':
            raise BadSpecError(
                _('Report contains invalid referenced_doc_type: {}').format(self.referenced_doc_type))

    def _get_domain_filter_spec(self):
        return {
            "type": "boolean_expression",
            "expression": {
                "type": "property_name",
                "property_name": "domain",
            },
            "operator": "in",
            "property_value": self.data_domains,
        }

    @property
    @memoized
    def default_indicators(self):
        default_indicators = super().default_indicators
        default_indicators.append(IndicatorFactory.from_spec({
            "column_id": "commcare_project",
            "type": "expression",
            "display_name": "Project Space",
            "datatype": "string",
            "is_nullable": False,
            "create_index": True,
            "expression": {
                "type": "root_doc",
                "expression": {
                    "type": "property_name",
                    "property_name": "domain"
                }
            }
        }, self.get_factory_context()))
        return default_indicators

    @classmethod
    def by_domain(cls, domain):
        return get_registry_data_sources_by_domain(domain)

    @classmethod
    def all_ids(cls):
        return get_all_registry_data_source_ids()

    def get_report_count(self):
        """
        Return the number of ReportConfigurations that reference this data source.
        """
        return RegistryReportConfiguration.count_by_data_source(self.domain, self._id)


class ReportMeta(DocumentSchema):
    # `True` if this report was initially constructed by the report builder.
    created_by_builder = BooleanProperty(default=False)
    report_builder_version = StringProperty(default="")
    # `True` if this report was ever edited in the advanced JSON UIs (after June 7, 2016)
    edited_manually = BooleanProperty(default=False)
    last_modified = DateTimeProperty()
    builder_report_type = StringProperty(choices=['chart', 'list', 'table', 'worker', 'map'])
    builder_source_type = StringProperty(choices=REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES)

    # If this is a linked report, this is the ID of the report this pulls from
    master_id = StringProperty()


class ReportConfiguration(QuickCachedDocumentMixin, Document):
    """
    A report configuration. These map 1:1 with reports that show up in the UI.
    """
    domain = StringProperty(required=True)
    visible = BooleanProperty(default=True)
    # config_id of the datasource
    config_id = StringProperty(required=True)
    data_source_type = StringProperty(default=DATA_SOURCE_TYPE_STANDARD,
                                      choices=[DATA_SOURCE_TYPE_STANDARD, DATA_SOURCE_TYPE_AGGREGATE])
    title = StringProperty()
    description = StringProperty()
    aggregation_columns = StringListProperty()
    filters = ListProperty()
    columns = ListProperty()
    configured_charts = ListProperty()
    sort_expression = ListProperty()
    distinct_on = ListProperty()
    soft_rollout = DecimalProperty(default=0)  # no longer used
    report_meta = SchemaProperty(ReportMeta)
    custom_query_provider = StringProperty(required=False)

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def __str__(self):
        return '{} - {}'.format(self.domain, self.title)

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
        return get_datasource_config(self.config_id, self.domain, self.data_source_type)[0]

    @property
    @memoized
    def report_columns(self):
        return [ReportColumnFactory.from_spec(c, self.is_static, self.domain) for c in self.columns]

    @property
    @memoized
    def report_columns_by_column_id(self):
        return {c.column_id: c for c in self.report_columns}

    @property
    @memoized
    def ui_filters(self):
        return [ReportFilterFactory.from_spec(f, self) for f in self.filters]

    @property
    @memoized
    def charts(self):
        if (
            self.config_id and self.configured_charts
            and toggles.SUPPORT_EXPANDED_COLUMN_IN_REPORTS.enabled(self.domain)
        ):
            configured_charts = deepcopy(self.configured_charts)
            for chart in configured_charts:
                if chart['type'] == 'multibar':
                    chart['y_axis_columns'] = self._get_expanded_y_axis_cols_for_multibar(chart['y_axis_columns'])
            return [ChartFactory.from_spec(g._obj) for g in configured_charts]
        else:
            return [ChartFactory.from_spec(g._obj) for g in self.configured_charts]

    def _get_expanded_y_axis_cols_for_multibar(self, original_y_axis_columns):
        y_axis_columns = []
        try:
            for y_axis_column in original_y_axis_columns:
                column_id = y_axis_column['column_id']
                column_config = self.report_columns_by_column_id[column_id]
                if column_config.type == 'expanded':
                    expanded_columns = self.get_expanded_columns(column_config)
                    for column in expanded_columns:
                        y_axis_columns.append({
                            'column_id': column.slug,
                            'display': column.header
                        })
                else:
                    y_axis_columns.append(y_axis_column)
        # catch edge cases where data source table is yet to be created
        except DataSourceConfigurationNotFoundError:
            return original_y_axis_columns
        else:
            return y_axis_columns

    def get_expanded_columns(self, column_config):
        return get_expanded_column_config(
            self.cached_data_source.config,
            column_config,
            self.cached_data_source.lang
        ).columns

    @property
    @memoized
    def cached_data_source(self):
        from corehq.apps.userreports.reports.data_source import (
            ConfigurableReportDataSource,
        )
        return ConfigurableReportDataSource.from_spec(self).data_source

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
                'columns': [x for x in (map_col(col) for col in self.columns) if x]
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
            if isinstance(item.get('display'), dict):
                langs |= set(item['display'].keys())
        return langs

    def validate(self, required=True):
        from corehq.apps.userreports.reports.data_source import (
            ConfigurableReportDataSource,
        )

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
        ConfigurableReportDataSource.from_spec(self)
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


class RegistryReportConfiguration(ReportConfiguration):

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def by_domain(cls, domain):
        return get_registry_report_configs_for_domain(domain)

    @classmethod
    @quickcache(['cls.__name__', 'domain', 'data_source_id'])
    def count_by_data_source(cls, domain, data_source_id):
        return get_number_of_registry_report_configs_by_data_source(domain, data_source_id)

    @property
    def registry_slug(self):
        return self.config.registry_slug

    @cached_property
    def registry_helper(self):
        return DataRegistryHelper(self.domain, registry_slug=self.registry_slug)

    @property
    @memoized
    def config(self):
        try:
            config = get_document_or_not_found(RegistryDataSourceConfiguration, self.domain, self.config_id)
        except DocumentNotFound:
            raise DataSourceConfigurationNotFoundError(_(
                'The data source referenced by this report could not be found.'
            ))
        return config


class StaticDataSourceConfiguration(JsonObject):
    """
    For custom data sources maintained in the repository.

    This class keeps the full list of static data source configurations relevant to the
    current environment in memory and upon requests builds a new data source configuration
    from the static config.

    See 0002-keep-static-ucr-configurations-in-memory.md
    """
    _datasource_id_prefix = STATIC_PREFIX
    domains = ListProperty(required=True)
    server_environment = ListProperty(required=True)
    config = DictProperty()
    mirrored_engine_ids = SchemaListProperty(MirroredEngineIds)

    @classmethod
    def get_doc_id(cls, domain, table_id):
        return '{}{}-{}'.format(cls._datasource_id_prefix, domain, table_id)

    @classmethod
    @memoized
    def by_id_mapping(cls):
        """Memoized method that maps domains to static data source config"""
        return {
            cls.get_doc_id(domain, wrapped.config['table_id']): (domain, wrapped)
            for wrapped in cls._all()
            for domain in wrapped.domains
        }

    @classmethod
    def _all(cls):
        """
        :return: Generator of all wrapped configs read from disk
        """
        def __get_all():
            paths = list(settings.STATIC_DATA_SOURCES)
            paths.extend(static_ucr_data_source_paths())
            for path_or_glob in paths:
                if os.path.isfile(path_or_glob):
                    yield _get_wrapped_object_from_file(path_or_glob, cls)
                else:
                    files = glob.glob(path_or_glob)
                    for path in files:
                        yield _get_wrapped_object_from_file(path, cls)

            for provider_path in settings.STATIC_DATA_SOURCE_PROVIDERS:
                provider_fn = to_function(provider_path, failhard=True)
                for wrapped, path in provider_fn():
                    yield wrapped

        return __get_all() if settings.UNIT_TESTING else _filter_by_server_env(__get_all())

    @classmethod
    def all(cls):
        """Unoptimized method that get's all configs by re-reading from disk"""
        for wrapped in cls._all():
            for domain in wrapped.domains:
                yield cls._get_datasource_config(wrapped, domain)

    @classmethod
    def by_domain(cls, domain):
        return [
            cls._get_datasource_config(wrapped, dom)
            for dom, wrapped in cls.by_id_mapping().values()
            if domain == dom
        ]

    @classmethod
    def by_id(cls, config_id):
        try:
            domain, wrapped = cls.by_id_mapping()[config_id]
        except KeyError:
            raise StaticDataSourceConfigurationNotFoundError(_(
                'The data source %(config_id)s referenced by this report could not be found.'
            ) % {'config_id': config_id})

        return cls._get_datasource_config(wrapped, domain)

    @classmethod
    def _get_datasource_config(cls, static_config, domain):
        doc = deepcopy(static_config.to_json()['config'])
        doc['domain'] = domain
        doc['_id'] = cls.get_doc_id(domain, doc['table_id'])

        def _get_mirrored_engine_ids():
            for env in static_config.mirrored_engine_ids:
                if env.server_environment == settings.SERVER_ENVIRONMENT:
                    return env.engine_ids
            return []
        doc['mirrored_engine_ids'] = _get_mirrored_engine_ids()
        return DataSourceConfiguration.wrap(doc)


class StaticReportConfiguration(JsonObject):
    """
    For statically defined reports based off of custom data sources

    This class keeps the full list of static report configurations relevant to the
    current environment in memory and upon requests builds a new report configuration
    from the static report config.

    See 0002-keep-static-ucr-configurations-in-memory.md
    """
    domains = ListProperty(required=True)
    report_id = StringProperty(validators=(_check_ids))
    data_source_table = StringProperty()
    config = DictProperty()
    custom_configurable_report = StringProperty()
    server_environment = ListProperty(required=True)

    @classmethod
    def get_doc_id(cls, domain, report_id, custom_configurable_report):
        return '{}{}-{}'.format(
            STATIC_PREFIX if not custom_configurable_report else CUSTOM_REPORT_PREFIX,
            domain,
            report_id,
        )

    @classmethod
    def _all(cls):
        def __get_all():
            paths = list(settings.STATIC_UCR_REPORTS)
            paths.extend(static_ucr_report_paths())
            for path_or_glob in paths:
                if os.path.isfile(path_or_glob):
                    yield _get_wrapped_object_from_file(path_or_glob, cls)
                else:
                    files = glob.glob(path_or_glob)
                    for path in files:
                        yield _get_wrapped_object_from_file(path, cls)

        filter_by_env = settings.UNIT_TESTING or settings.DEBUG
        return __get_all() if filter_by_env else _filter_by_server_env(__get_all())

    @classmethod
    @memoized
    def by_id_mapping(cls):
        return {
            cls.get_doc_id(domain, wrapped.report_id, wrapped.custom_configurable_report): (domain, wrapped)
            for wrapped in cls._all()
            for domain in wrapped.domains
        }

    @classmethod
    def all(cls):
        """Only used in tests"""
        for wrapped in StaticReportConfiguration._all():
            for domain in wrapped.domains:
                yield cls._get_report_config(wrapped, domain)

    @classmethod
    def by_domain(cls, domain):
        """
        Returns a list of ReportConfiguration objects, NOT StaticReportConfigurations.
        """
        return [
            cls._get_report_config(wrapped, dom)
            for dom, wrapped in cls.by_id_mapping().values()
            if domain == dom
        ]

    @classmethod
    def by_id(cls, config_id, domain):
        """Returns a ReportConfiguration object, NOT StaticReportConfigurations.
        """
        try:
            report_domain, wrapped = cls.by_id_mapping()[config_id]
        except KeyError:
            raise BadSpecError(_('The report configuration referenced by this report could '
                                 'not be found: %(report_id)s') % {'report_id': config_id})

        if domain and report_domain != domain:
            raise DocumentNotFound("Document {} of class {} not in domain {}!".format(
                config_id,
                ReportConfiguration.__class__.__name__,
                domain,
            ))
        return cls._get_report_config(wrapped, report_domain)

    @classmethod
    def by_ids(cls, config_ids):
        mapping = cls.by_id_mapping()
        config_by_ids = {}
        for config_id in set(config_ids):
            try:
                domain, wrapped = mapping[config_id]
            except KeyError:
                raise ReportConfigurationNotFoundError(_(
                    "The following report configuration could not be found: {}".format(config_id)
                ))
            config_by_ids[config_id] = cls._get_report_config(wrapped, domain)
        return config_by_ids

    @classmethod
    def report_class_by_domain_and_id(cls, domain, config_id):
        try:
            report_domain, wrapped = cls.by_id_mapping()[config_id]
        except KeyError:
            raise BadSpecError(
                _('The report configuration referenced by this report could not be found.')
            )
        if report_domain != domain:
            raise DocumentNotFound("Document {} of class {} not in domain {}!".format(
                config_id,
                ReportConfiguration.__class__.__name__,
                domain,
            ))
        return wrapped.custom_configurable_report

    @classmethod
    def _get_report_config(cls, static_config, domain):
        doc = copy(static_config.to_json()['config'])
        doc['domain'] = domain
        doc['_id'] = cls.get_doc_id(domain, static_config.report_id, static_config.custom_configurable_report)
        doc['config_id'] = StaticDataSourceConfiguration.get_doc_id(domain, static_config.data_source_table)
        return ReportConfiguration.wrap(doc)


class AsyncIndicator(models.Model):
    """Indicator that has not yet been processed

    These indicators will be picked up by a queue and placed into celery to be
    saved. Once saved to the data sources, this record will be deleted
    """
    id = models.BigAutoField(primary_key=True)
    doc_id = models.CharField(max_length=255, null=False, unique=True)
    doc_type = models.CharField(max_length=126, null=False)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    indicator_config_ids = ArrayField(
        models.CharField(max_length=126, null=True, blank=True),
        null=False
    )
    date_created = models.DateTimeField(auto_now_add=True, db_index=True)
    date_queued = models.DateTimeField(null=True, db_index=True)
    unsuccessful_attempts = models.IntegerField(default=0)

    class Meta(object):
        ordering = ["date_created"]

    @classmethod
    def update_record(cls, doc_id, doc_type, domain, config_ids):
        if not isinstance(config_ids, list):
            config_ids = list(config_ids)
        config_ids = sorted(config_ids)

        indicator, created = cls.objects.get_or_create(
            doc_id=doc_id, doc_type=doc_type, domain=domain,
            defaults={'indicator_config_ids': config_ids}
        )

        if created:
            return indicator
        elif set(config_ids) == indicator.indicator_config_ids:
            return indicator

        with CriticalSection([get_async_indicator_modify_lock_key(doc_id)]):
            # Add new config ids. Need to grab indicator again in case it was
            # processed since we called get_or_create
            try:
                indicator = cls.objects.get(doc_id=doc_id)
            except cls.DoesNotExist:
                indicator = AsyncIndicator.objects.create(
                    doc_id=doc_id,
                    doc_type=doc_type,
                    domain=domain,
                    indicator_config_ids=config_ids
                )
            else:
                current_config_ids = set(indicator.indicator_config_ids)
                config_ids = set(config_ids)
                if config_ids - current_config_ids:
                    new_config_ids = sorted(list(current_config_ids.union(config_ids)))
                    indicator.indicator_config_ids = new_config_ids
                    indicator.unsuccessful_attempts = 0
                    indicator.save()

        return indicator

    @classmethod
    def update_from_kafka_change(cls, change, config_ids):
        return cls.update_record(
            change.id, change.document['doc_type'], change.document['domain'], config_ids
        )

    def update_failure(self, to_remove):
        self.refresh_from_db(fields=['indicator_config_ids'])
        new_indicators = set(self.indicator_config_ids) - set(to_remove)
        self.indicator_config_ids = sorted(list(new_indicators))
        self.unsuccessful_attempts += 1
        self.date_queued = None

    @classmethod
    def bulk_creation(cls, doc_ids, doc_type, domain, config_ids):
        """Ignores the locking in update_record

        Should only be used if you know the table is not otherwise being used,
        and the doc ids you're supplying are not currently being used in another
        asynchronous table.

        For example the first build of a table, or any complete rebuilds.

        If after reading the above and you're still wondering whether it's safe
        to use, don't.
        """

        AsyncIndicator.objects.bulk_create([
            AsyncIndicator(doc_id=doc_id, doc_type=doc_type, domain=domain, indicator_config_ids=config_ids)
            for doc_id in doc_ids
        ])

    @classmethod
    def bulk_update_records(cls, configs_by_docs, domain, doc_type_by_id):
        # type (Dict[str, List[str]], str, Dict[str, str]) -> None
        # configs_by_docs should be a dict of doc_id -> list of config_ids
        if not configs_by_docs:
            return
        doc_ids = list(configs_by_docs.keys())

        current_indicators = AsyncIndicator.objects.filter(doc_id__in=doc_ids).all()
        to_update = []

        for indicator in current_indicators:
            new_configs = set(configs_by_docs[indicator.doc_id])
            current_configs = set(indicator.indicator_config_ids)
            if not new_configs.issubset(current_configs):
                indicator.indicator_config_ids = sorted(current_configs.union(new_configs))
                indicator.unsuccessful_attempts = 0
                to_update.append(indicator)
        if to_update:
            bulk_update_helper(to_update)

        new_doc_ids = set(doc_ids) - set([i.doc_id for i in current_indicators])
        AsyncIndicator.objects.bulk_create([
            AsyncIndicator(doc_id=doc_id, doc_type=doc_type_by_id[doc_id], domain=domain,
                           indicator_config_ids=sorted(configs_by_docs[doc_id]))
            for doc_id in new_doc_ids
        ])


class InvalidUCRData(models.Model):
    doc_id = models.CharField(max_length=255, null=False)
    doc_type = models.CharField(max_length=126, null=False, db_index=True)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    indicator_config_id = models.CharField(max_length=126, db_index=True)
    date_created = models.DateTimeField(auto_now_add=True, db_index=True)
    validation_name = models.TextField()
    validation_text = models.TextField()
    notes = models.TextField(null=True)

    class Meta(object):
        unique_together = ('doc_id', 'indicator_config_id', 'validation_name')


class UCRExpressionManager(models.Manager):
    def get_expressions_for_domain(self, domain):
        return self.filter(domain=domain, expression_type=UCR_NAMED_EXPRESSION)

    def get_filters_for_domain(self, domain):
        return self.filter(domain=domain, expression_type=UCR_NAMED_FILTER)

    def get_wrapped_filters_for_domain(self, domain, factory_context):
        return {
            f.name: f.wrapped_definition(factory_context)
            for f in self.filter(domain=domain, expression_type=UCR_NAMED_FILTER)
        }

    def get_wrapped_expressions_for_domain(self, domain, factory_context):
        return {
            f.name: f.wrapped_definition(factory_context)
            for f in self.get_expressions_for_domain(domain)
        }


class UCRExpression(models.Model):
    """
    A single UCR named expression or named filter that can
    be shared amongst features that use these
    """
    name = models.CharField(max_length=255, null=False)
    domain = models.CharField(max_length=255, null=False, db_index=True)
    description = models.TextField(blank=True, null=True)
    expression_type = models.CharField(
        max_length=20, default=UCR_NAMED_EXPRESSION, choices=ALL_EXPRESSION_TYPES, db_index=True
    )
    definition = models.JSONField(null=True)

    # For use with linked domains - the upstream UCRExpression
    upstream_id = models.CharField(max_length=126, null=True)
    LINKED_DOMAIN_UPDATABLE_PROPERTIES = [
        "name", "description", "expression_type", "definition"
    ]

    objects = UCRExpressionManager()

    class Meta:
        app_label = 'userreports'
        unique_together = ('name', 'domain')

    def wrapped_definition(self, factory_context):
        if self.expression_type == UCR_NAMED_EXPRESSION:
            return ExpressionFactory.from_spec(self.definition, factory_context)
        elif self.expression_type == UCR_NAMED_FILTER:
            return FilterFactory.from_spec(self.definition, factory_context)

    def update_from_upstream(self, upstream_ucr_expression):
        """
        For use with linked domains. Updates this ucr expression with data from `upstream_ucr_expression`
        """
        for prop in self.LINKED_DOMAIN_UPDATABLE_PROPERTIES:
            setattr(self, prop, getattr(upstream_ucr_expression, prop))
        self.save()

    def __str__(self):
        description = self.description
        if len(self.description) > 64:
            description = f"{self.description[:64]}…"
        description = f": {description}" if description else ""
        return f"{self.name}{description}"


def get_datasource_config_infer_type(config_id, domain):
    return get_datasource_config(config_id, domain, guess_data_source_type(config_id))


def guess_data_source_type(data_source_id):
    """
    Given a data source ID, try to guess its type (standard or aggregate).
    """
    # ints are definitely aggregate
    if isinstance(data_source_id, int):
        return DATA_SOURCE_TYPE_AGGREGATE
    # static ids are standard
    if id_is_static(data_source_id):
        return DATA_SOURCE_TYPE_STANDARD
    try:
        # uuids are standard
        UUID(data_source_id)
        return DATA_SOURCE_TYPE_STANDARD
    except ValueError:
        try:
            # int-like-things are aggregate
            int(data_source_id)
            return DATA_SOURCE_TYPE_AGGREGATE
        except ValueError:
            # default should be standard
            return DATA_SOURCE_TYPE_STANDARD


def get_datasource_config(config_id, domain, data_source_type=DATA_SOURCE_TYPE_STANDARD):
    def _raise_not_found():
        raise DataSourceConfigurationNotFoundError(_(
            'The data source referenced by this report could not be found.'
        ))

    if data_source_type == DATA_SOURCE_TYPE_STANDARD:
        is_static = id_is_static(config_id)
        if is_static:
            config = StaticDataSourceConfiguration.by_id(config_id)
            if config.domain != domain:
                _raise_not_found()
        else:
            try:
                config = get_document_or_not_found(DataSourceConfiguration, domain, config_id)
            except DocumentNotFound:
                try:
                    config = get_document_or_not_found(RegistryDataSourceConfiguration, domain, config_id)
                except DocumentNotFound:
                    _raise_not_found()
        return config, is_static
    elif data_source_type == DATA_SOURCE_TYPE_AGGREGATE:
        from corehq.apps.aggregate_ucrs.models import AggregateTableDefinition
        try:
            config = AggregateTableDefinition.objects.get(id=int(config_id), domain=domain)
            return config, False
        except AggregateTableDefinition.DoesNotExist:
            _raise_not_found()
    else:
        raise InvalidDataSourceType('{} is not a valid data source type!'.format(data_source_type))


def id_is_static(data_source_id):
    if data_source_id is None:
        return False
    return data_source_id.startswith(StaticDataSourceConfiguration._datasource_id_prefix)


def report_config_id_is_static(config_id):
    """
    Return True if the given report configuration id refers to a static report
    configuration.
    """
    if config_id is None:
        return False
    return any(
        config_id.startswith(prefix)
        for prefix in [STATIC_PREFIX, CUSTOM_REPORT_PREFIX]
    )


def is_data_registry_report(report_config, datasource=None):
    """
    The optional datasource parameter is useful when checking a report config fetched from a remote server
    """
    datasource = datasource or report_config.config
    return isinstance(report_config, RegistryReportConfiguration) or datasource.meta.build.registry_slug


def get_report_configs(config_ids, domain):
    """
    Return a list of ReportConfigurations.
    config_ids may be ReportConfiguration or StaticReportConfiguration ids.
    """

    static_report_config_ids = []
    dynamic_report_config_ids = []
    for config_id in set(config_ids):
        if report_config_id_is_static(config_id):
            static_report_config_ids.append(config_id)
        else:
            dynamic_report_config_ids.append(config_id)
    static_report_config_by_ids = StaticReportConfiguration.by_ids(static_report_config_ids)
    static_report_configs = list(static_report_config_by_ids.values())
    if len(static_report_configs) != len(static_report_config_ids):
        raise ReportConfigurationNotFoundError
    for config in static_report_configs:
        if config.domain != domain:
            raise ReportConfigurationNotFoundError

    dynamic_report_configs = []
    if dynamic_report_config_ids:
        dynamic_report_configs = [
            wrap_report_config_by_type(doc) for doc in
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


def _get_wrapped_object_from_file(path, wrapper):
    with open(path, encoding='utf-8') as f:
        if path.endswith('.json'):
            doc = json.load(f)
        else:
            doc = yaml.safe_load(f)

    try:
        return wrapper.wrap(doc)
    except Exception as ex:
        msg = '{}: {}'.format(path, ex.args[0]) if ex.args else str(path)
        ex.args = (msg,) + ex.args[1:]
        raise


def _filter_by_server_env(configs):
    for wrapped in configs:
        if wrapped.server_environment and settings.SERVER_ENVIRONMENT not in wrapped.server_environment:
            continue
        yield wrapped


_Validation = namedtuple('_Validation', 'name error_message validation_function')


class FilterValueEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, DateSpan):
            return str(obj)
        return super(FilterValueEncoder, self).default(obj)
