import datetime
import uuid
from abc import ABCMeta, abstractmethod
from collections import OrderedDict, namedtuple

from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from memoized import memoized

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_case_properties,
)
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.xform import XForm
from corehq.apps.case_search.const import COMMCARE_PROJECT
from corehq.apps.data_dictionary.util import get_data_dict_props_by_case_type
from corehq.apps.domain.models import DomainAuditRecordEntry
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.utils import RegistryPermissionCheck
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager.data_source_meta import (
    APP_DATA_SOURCE_TYPE_VALUES,
    DATA_SOURCE_TYPE_RAW,
    REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES,
    DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM,
    make_case_data_source_filter, make_form_data_source_filter,
)
from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.const import DATA_SOURCE_MISSING_APP_ERROR_MESSAGE, LENIENT_MAXIMUM_EXPANSION
from corehq.apps.userreports.exceptions import BadBuilderConfigError
from corehq.apps.userreports.models import (
    DataSourceBuildInformation,
    DataSourceConfiguration,
    DataSourceMeta,
    ReportConfiguration,
    ReportMeta,
    get_datasource_config_infer_type,
    guess_data_source_type,
    RegistryDataSourceConfiguration, RegistryReportConfiguration,
)
from corehq.apps.userreports.dbaccessors import get_report_and_registry_report_configs_for_domain
from corehq.apps.userreports.reports.builder import (
    DEFAULT_CASE_PROPERTY_DATATYPES,
    FORM_METADATA_PROPERTIES,
    get_filter_format_from_question_type,
    const)
from corehq.apps.userreports.reports.builder.columns import (
    CasePropertyColumnOption,
    CountColumn,
    FormMetaColumnOption,
    MultiselectQuestionColumnOption,
    OwnernameComputedCasePropertyOption,
    QuestionColumnOption,
    RawPropertyColumnOption,
    UsernameComputedCasePropertyOption,
)
from corehq.apps.userreports.reports.builder.const import (
    COMPUTED_OWNER_LOCATION_PROPERTY_ID,
    COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
    COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID,
    COMPUTED_OWNER_NAME_PROPERTY_ID,
    COMPUTED_USER_NAME_PROPERTY_ID,
    PROPERTY_TYPE_CASE_PROP,
    PROPERTY_TYPE_META,
    PROPERTY_TYPE_QUESTION,
    PROPERTY_TYPE_RAW,
    UCR_AGG_AVG,
    UCR_AGG_EXPAND,
    UCR_AGG_SIMPLE,
    UCR_AGG_SUM,
    UI_AGG_AVERAGE,
    UI_AGG_COUNT_PER_CHOICE,
    UI_AGG_GROUP_BY,
    UI_AGG_SUM,
)
from corehq.apps.userreports.reports.builder.filter_formats import get_pre_filter_format
from corehq.apps.userreports.reports.builder.sources import (
    get_source_type_from_report_config,
)
from corehq.apps.userreports.sql import get_column_name
from corehq.apps.userreports.ui.fields import JsonField
from corehq.apps.userreports.util import has_report_builder_access, get_ucr_datasource_config_by_id
from corehq.toggles import (
    SHOW_RAW_DATA_SOURCES_IN_REPORT_BUILDER,
    OVERRIDE_EXPANDED_COLUMN_LIMIT_IN_REPORT_BUILDER,
    SHOW_IDS_IN_REPORT_BUILDER,
    DATA_REGISTRY_UCR
)
from dimagi.utils.couch.undo import undo_delete
from corehq.toggles import SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE


STATIC_CASE_PROPS = [
    "closed",
    "closed_on",
    "modified_on",
    "name",
    "opened_on",
    "owner_id",
    "user_id",
]

# PostgreSQL limit = 1600. Sane limit = 500?
MAX_COLUMNS = 500
TEMP_DATA_SOURCE_LIFESPAN = 24 * 60 * 60
SAMPLE_DATA_MAX_ROWS = 100


class FilterField(JsonField):
    """
    A form field with a little bit of validation for report builder report
    filter configuration.
    """

    def validate(self, value):
        super(FilterField, self).validate(value)
        for filter_conf in value:
            if filter_conf.get('format', None) not in (list(const.REPORT_BUILDER_FILTER_TYPE_MAP) + [""]):
                raise forms.ValidationError("Invalid filter format!")


class DataSourceProperty(object):
    """
    A container class for information about data source properties

    Class attributes:

    type -- either "case_property", "question", "meta", or "raw"
    id -- A string that uniquely identifies this property. For question based
        properties this is the question id, for case based properties this is
        the case property name.
    text -- A human readable representation of the property source. For
        questions this is the question label.
    source -- For questions, this is a dict representing the question as returned
        by Xform.get_questions(), for case properties and form metadata it is just
        the name of the property.
    data_types
    """

    def __init__(self, type, id, text, source, data_types):
        self._type = type
        self._id = id
        self._text = text
        self._source = source
        self._data_types = data_types

    def to_view_model(self):
        """
        Return a dictionary representation to be used by the js
        """
        return {
            "type": self._type,
            "id": self._id,
            "text": self._text,
            "source": self._source,
        }

    def get_text(self):
        return self._text

    def get_type(self):
        return self._type

    def get_id(self):
        return self._id

    def get_source(self):
        return self._source

    def to_report_column_option(self):
        if self._type == PROPERTY_TYPE_QUESTION:
            if self._source['type'] == "MSelect":
                return MultiselectQuestionColumnOption(self._id, self._text, self._source)
            else:
                return QuestionColumnOption(self._id, self._data_types, self._text, self._source)
        elif self._type == PROPERTY_TYPE_META:
            return FormMetaColumnOption(self._id, self._data_types, self._text, self._source)
        elif self._type == PROPERTY_TYPE_CASE_PROP:
            if self._id in (
                COMPUTED_OWNER_NAME_PROPERTY_ID,
                COMPUTED_OWNER_LOCATION_PROPERTY_ID,
                COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
                COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID
            ):
                return OwnernameComputedCasePropertyOption(self._id, self._data_types, self._text)
            elif self._id == COMPUTED_USER_NAME_PROPERTY_ID:
                return UsernameComputedCasePropertyOption(self._id, self._data_types, self._text)
            else:
                return CasePropertyColumnOption(self._id, self._data_types, self._text)
        else:
            assert self._type == PROPERTY_TYPE_RAW
            return RawPropertyColumnOption(self._id, self._data_types, self._text, self._source)

    def _get_filter_format(self, filter_configuration):
        """
        Return the UCR filter type that should be used for the given filter configuration (passed from the UI).
        """
        selected_filter_type = filter_configuration['format']
        if not selected_filter_type or self._type in ('question', 'meta'):
            if self._type == 'question':
                filter_format = get_filter_format_from_question_type(self._source['type'])
            else:
                assert self._type == 'meta'
                filter_format = get_filter_format_from_question_type(self._source[1])
        else:
            filter_format = const.REPORT_BUILDER_FILTER_TYPE_MAP[selected_filter_type]
        return filter_format

    def _get_ui_aggregation_for_filter_format(self, filter_format):
        """
        ColumnOption._get_indicator(aggregation) uses the aggregation type to determine what data type the
        indicator should be. Therefore, we need to convert filter formats to aggregation types so that we can
        create the correct type of indicator.
        """
        if filter_format == "numeric":
            return UI_AGG_SUM  # This could also be UI_AGG_AVERAGE, just needs to force numeric
        else:
            return UI_AGG_GROUP_BY

    def to_report_filter(self, configuration, index):
        """
        Return a UCR report filter configuration for the given configuration.
        :param configuration:  dictionary representing options selected in UI.
        :param index: Index of this filter in the list of filters configured by the user.
        :return:
        """
        filter_format = self._get_filter_format(configuration)
        ui_aggregation = self._get_ui_aggregation_for_filter_format(filter_format)
        column_id = self.to_report_column_option().get_indicators(ui_aggregation)[0]['column_id']

        filter = {
            "field": column_id,
            "slug": "{}_{}".format(column_id, index),
            "display": configuration["display_text"],
            "type": filter_format
        }
        if configuration['format'] == const.FORMAT_DATE:
            filter.update({'compare_as_string': True})

        if filter_format == 'dynamic_choice_list' and self._id == COMPUTED_OWNER_NAME_PROPERTY_ID:
            filter.update({"choice_provider": {"type": "owner"}})
        if filter_format == 'dynamic_choice_list' and self._id == COMPUTED_USER_NAME_PROPERTY_ID:
            filter.update({"choice_provider": {"type": "user"}})
        if filter_format == 'dynamic_choice_list' and self._id == COMPUTED_OWNER_LOCATION_PROPERTY_ID:
            filter.update({"choice_provider": {"type": "location"}})
        if (
            filter_format == 'dynamic_choice_list'
            and self._id == COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID
        ):
            filter.update({"choice_provider": {"type": "location", "include_descendants": True}})
        if (
            filter_format == 'dynamic_choice_list'
            and self._id == COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID
        ):
            filter.update(
                {
                    "choice_provider": {
                        "type": "location",
                        "include_descendants": True,
                        "show_all_locations": True
                    }
                }
            )
        if filter_format == 'dynamic_choice_list' and self._id == COMMCARE_PROJECT:
            filter.update({"choice_provider": {"type": COMMCARE_PROJECT}})
        if configuration.get('pre_value') or configuration.get('pre_operator'):
            filter.update({
                'type': 'pre',  # type could have been "date"
                'pre_operator': configuration.get('pre_operator', None),
                'pre_value': configuration.get('pre_value', []),
            })
        if configuration['format'] == const.PRE_FILTER_VALUE_IS_EMPTY:
            filter.update({
                'type': 'pre',
                'pre_operator': "",
                'pre_value': "",  # for now assume strings - this may not always work but None crashes
            })
        if configuration['format'] == const.PRE_FILTER_VALUE_EXISTS:
            filter.update({
                'type': 'pre',
                'pre_operator': "!=",
                'pre_value': "",
            })
        if configuration['format'] == const.PRE_FILTER_VALUE_NOT_EQUAL:
            filter.update({
                'type': 'pre',
                'pre_operator': "distinct from",
                # pre_value already set by "pre" clause
            })
        return filter

    def to_report_filter_indicator(self, configuration):
        """
        Return the indicator that would correspond to the given filter configuration
        """
        filter_format = self._get_filter_format(configuration)
        ui_aggregation = self._get_ui_aggregation_for_filter_format(filter_format)
        return self.to_report_column_option()._get_indicator(ui_aggregation)


class ReportBuilderDataSourceInterface(metaclass=ABCMeta):
    """
    Abstract interface to a data source in report builder.

    A data source could be an (app, form), (app, case_type), or (registry, case_type) pair (see
    ManagedReportBuilderDataSourceHelper), or it can be a real UCR data source (see UnmanagedDataSourceHelper)
    """

    @property
    @abstractmethod
    def report_config_class(self):
        """Return the report class type"""
        raise NotImplementedError

    @property
    @abstractmethod
    def uses_managed_data_source(self):
        """
        Whether this interface uses a managed data source.

        If true, the data source will be created / modified with the report, and the
        temporary data source workflow will be enabled.

        If false, the data source is assumed to exist and be available as self.data_source_id.

        :return:
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def data_source_properties(self):
        """
        A dictionary containing the various properties that may be used as indicators
        or columns in the data source or report.

        Keys are strings that uniquely identify properties.
        Values are DataSourceProperty instances.

        >> self.data_source_properties
        {
            "/data/question1": DataSourceProperty(
                type="question",
                id="/data/question1",
                text="Enter the child's name",
                source={
                    'repeat': None,
                    'group': None,
                    'value': '/data/question1',
                    'label': 'question1',
                    'tag': 'input',
                    'type': 'Text'
                },
                data_types=["string"]
            ),
            "meta/deviceID": DataSourceProperty(
                type="meta",
                id="meta/deviceID",
                text="deviceID",
                source=("deviceID", "string"),
                data_types=["string"]
            )
        }
        """
        pass

    @property
    @abstractmethod
    def report_column_options(self):
        pass


class ManagedReportBuilderDataSourceHelper(ReportBuilderDataSourceInterface):
    """Abstract class that represents the interface required for building managed
    data sources

    When configuring a report, one can use ManagedReportBuilderDataSourceHelper to determine some
    of the properties of the required report data source, such as:
        - referenced doc type
        - filter
        - indicators
    """

    def __init__(self, domain, source_type, source_id):
        assert (source_type in ['case', 'form'])

        self.domain = domain
        self.source_type = source_type
        # case type or form ID
        self.source_id = source_id

    @property
    def uses_managed_data_source(self):
        return True

    @property
    def report_config_class(self):
        return RegistryReportConfiguration if self.uses_registry_data_source else ReportConfiguration

    @property
    def uses_registry_data_source(self):
        """
        Whether this interface uses a registry data source.

        If true, it will use RegistryDataSourceConfiguration.

        If false, it uses DataSourceConfiguration.

        :return:
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def source_doc_type(self):
        """Return the doc_type the datasource.referenced_doc_type"""
        raise NotImplementedError

    @property
    @abstractmethod
    def filter(self):
        """
        Return the filter configuration for the DataSourceConfiguration.
        """
        raise NotImplementedError

    @abstractmethod
    def base_item_expression(self, is_multiselect_chart_report, multiselect_field=None):
        raise NotImplementedError

    def indicators(self, columns, filters, as_dict=False):
        """
        Return a list of indicators to be used in a data source configuration that supports the given columns and
        indicators.
        :param columns: A list of objects representing columns in the report.
            Each object has a "property" and "calculation" key
        :param filters: A list of filter configuration objects
        """

        indicators = OrderedDict()
        for column in columns:
            # Property is only set if the column exists in report_column_options
            if column['property']:
                column_option = self.report_column_options[column['property']]
                for indicator in column_option.get_indicators(column['calculation']):
                    # A column may have multiple indicators. e.g. "Group By" and "Count Per Choice" aggregations
                    # will use one indicator for the field's string value, and "Sum" and "Average" aggregations
                    # will use a second indicator for the field's numerical value. "column_id" includes the
                    # indicator's data type, so it is unique per indicator ... except for choice list indicators,
                    # because they get expanded to one column per choice. The column_id of choice columns will end
                    # up unique because they will include a slug of the choice value. Here "column_id + type" is
                    # unique.
                    indicator_key = (indicator['column_id'], indicator['type'])
                    indicators.setdefault(indicator_key, indicator)

        for filter_ in filters:
            # Property is only set if the filter exists in report_column_options
            if filter_['property']:
                property_ = self.data_source_properties[filter_['property']]
                indicator = property_.to_report_filter_indicator(filter_)
                indicator_key = (indicator['column_id'], indicator['type'])
                indicators.setdefault(indicator_key, indicator)

        if as_dict:
            return indicators

        return list(indicators.values())

    def all_possible_indicators(self, required_columns, required_filters):
        """
        Will generate a set of possible indicators for the datasource making sure to include the
        provided columns and filters
        """
        indicators = self.indicators(required_columns, required_filters, as_dict=True)

        for column_option in self.report_column_options.values():
            for agg in column_option.aggregation_options:
                for indicator in column_option.get_indicators(agg):
                    indicator_key = (indicator['column_id'], indicator['type'])
                    indicators.setdefault(indicator_key, indicator)

        return list(indicators.values())[:MAX_COLUMNS]

    @property
    @abstractmethod
    def data_source_properties(self):
        raise NotImplementedError

    @property
    @memoized
    def report_column_options(self):
        options = OrderedDict()
        for id_, prop in self.data_source_properties.items():
            options[id_] = prop.to_report_column_option()

        # NOTE: Count columns aren't useful for table reports. But we need it in the column options because
        # the options are currently static, after loading the report builder a user can switch to an aggregated
        # report.
        count_col = CountColumn("Number of Cases" if self.source_type == "case" else "Number of Forms")
        options[count_col.get_property()] = count_col

        return options

    @property
    @abstractmethod
    def data_source_name(self):
        raise NotImplementedError

    def construct_data_source(self, table_id, **kwargs):
        return DataSourceConfiguration(domain=self.domain, table_id=table_id, **kwargs)

    def _ds_config_kwargs(self, indicators, is_multiselect_chart_report=False, multiselect_field=None):
        if is_multiselect_chart_report:
            base_item_expression = self.base_item_expression(True, multiselect_field)
        else:
            base_item_expression = self.base_item_expression(False)

        return dict(
            display_name=self.data_source_name,
            referenced_doc_type=self.source_doc_type,
            configured_filter=self.filter,
            configured_indicators=indicators,
            base_item_expression=base_item_expression,
            meta=DataSourceMeta(build=self._get_data_source_build_information())
        )

    def _get_data_source_build_information(self):
        raise NotImplementedError

    def get_temp_datasource_constructor_kwargs(self, required_columns, required_filters):
        indicators = self._remove_defaults_from_indicators(
            self.all_possible_indicators(required_columns, required_filters)
        )
        return self._ds_config_kwargs(indicators)

    def get_datasource_constructor_kwargs(self, columns, filters,
                                          is_multiselect_chart_report=False, multiselect_field=None):
        indicators = self._remove_defaults_from_indicators(
            self.indicators(columns, filters)
        )
        return self._ds_config_kwargs(indicators, is_multiselect_chart_report, multiselect_field)

    def _remove_defaults_from_indicators(self, indicators):
        defaults = self._get_datasource_default_columns()
        return [
            indicator for indicator in indicators
            if indicator['column_id'] not in defaults
        ]

    def _get_datasource_default_columns(self):
        return {
            column.id
            for indicator in DataSourceConfiguration().default_indicators
            for column in indicator.get_columns()
        }


class UnmanagedDataSourceHelper(ReportBuilderDataSourceInterface):
    """
    A ReportBuilderDataSourceInterface that encapsulates an existing data source.
    """

    def __init__(self, domain, app, source_type, source_id):
        assert source_type == 'data_source'
        self.domain = domain
        self.app = app
        self.source_type = source_type
        # source_id is the ID of a UCR data source
        self.data_source_id = source_id

    @property
    def uses_managed_data_source(self):
        return False

    @property
    def report_config_class(self):
        return {
            "DataSourceConfiguration": ReportConfiguration,
            "RegistryDataSourceConfiguration": RegistryReportConfiguration,
        }[self.data_source.doc_type]

    @property
    @memoized
    def data_source(self):
        return get_datasource_config_infer_type(self.data_source_id, self.domain)[0]

    @property
    def data_source_properties(self):
        def _data_source_property_from_ucr_column(column):
            # note: using column ID as the display text is a bummer but we don't have a a better
            # way to easily access a readable name for these yet
            return DataSourceProperty(
                type=PROPERTY_TYPE_RAW,
                id=column.id,
                text=column.id,
                source=column.id,
                data_types=[column.datatype],
            )

        properties = OrderedDict()
        for column in self.data_source.get_columns():
            properties[column.id] = _data_source_property_from_ucr_column(column)
        return properties

    @property
    def report_column_options(self):
        options = OrderedDict()
        for id_, prop in self.data_source_properties.items():
            options[id_] = prop.to_report_column_option()

        return options


class ApplicationFormDataSourceHelper(ManagedReportBuilderDataSourceHelper):
    def __init__(self, domain, app, source_type, source_id):
        assert source_type == 'form'
        self.app = app
        super().__init__(domain, source_type, source_id)
        self.source_form = self.app.get_form(source_id)
        self.source_xform = XForm(self.source_form.source, domain=app.domain)

    def base_item_expression(self, is_multiselect_chart_report, multiselect_field=None):
        """
        Return the base_item_expression for the DataSourceConfiguration.
        Normally this is {}, but if this is a data source for a chart report that is aggregated by a multiselect
        question, then we want one row per multiselect answer.
        :param is_multiselect_chart_report: True if the data source will be used for a chart report aggregated by
            a multiselect question.
        :param multiselect_field: The field that the multiselect aggregated report is aggregated by.
        :return: A base item expression.
        """
        if not is_multiselect_chart_report:
            return {}
        else:
            assert multiselect_field, "multiselect_field is required if is_multiselect_chart_report is True"

            property = self.data_source_properties[multiselect_field]
            path = ['form'] + property.get_source()['value'].split('/')[2:]
            choices = [c['value'] for c in property.get_source()['options']]

            def sub_doc(path):
                if not path:
                    return {"type": "property_name", "property_name": "choice"}
                else:
                    return {
                        "type": "dict",
                        "properties": {
                            path[0]: sub_doc(path[1:])
                        }
                    }

            return {
                "type": "map_items",
                "items_expression": {
                    "type": "iterator",
                    "expressions": [
                        {
                            "type": "dict",
                            "properties": {
                                "choice": c,
                                "doc": {"type": "identity"}
                            }
                        }
                        for c in choices
                    ],
                    "test": {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_path",
                            "property_path": ["doc"] + path
                        },
                        "operator": "in_multi",
                        "property_value": {"type": "property_name", "property_name": "choice"}
                    }
                },
                "map_expression": sub_doc(path)
            }

    @property
    def source_doc_type(self):
        return 'XFormInstance'

    @property
    def uses_registry_data_source(self):
        return False

    @property
    @memoized
    def filter(self):
        return make_form_data_source_filter(
            self.source_xform.data_node.tag_xmlns, self.source_form.get_app().get_id)

    @property
    @memoized
    def data_source_properties(self):
        property_map = {
            'username': _('User Name'),
            'userID': _('User ID'),
            'timeStart': _('Date Form Started'),
            'timeEnd': _('Date Form Completed'),
        }
        properties = OrderedDict()
        questions = self.source_xform.get_questions([], exclude_select_with_itemsets=True)
        for prop in FORM_METADATA_PROPERTIES:
            question_type = prop[1]
            data_type = {
                "DateTime": "datetime",
                "Text": "string",
            }[question_type]
            properties[prop[0]] = DataSourceProperty(
                type=PROPERTY_TYPE_META,
                id=prop[0],
                text=property_map.get(prop[0], prop[0]),
                source=prop,
                data_types=[data_type]
            )
        for question in questions:
            if question['type'] == "DataBindOnly":
                data_types = ["string", "decimal", "datetime"]
            elif question['type'] in ("Int", "Double", "Long"):
                data_types = ["decimal"]
            else:
                data_types = ["string"]
            properties[question['value']] = DataSourceProperty(
                type=PROPERTY_TYPE_QUESTION,
                id=question['value'],
                text=question['label'],
                source=question,
                data_types=data_types,
            )
        if self.source_form.get_app().auto_gps_capture:
            properties['location'] = DataSourceProperty(
                type=PROPERTY_TYPE_META,
                id='location',
                text='location',
                source=(['location', '#text'], 'Text'),
                data_types=["string"],
            )
        return properties

    def _get_data_source_build_information(self):
        return DataSourceBuildInformation(
            source_id=self.source_id,
            app_id=self.app._id,
            app_version=self.app.version,
        )

    @property
    @memoized
    def data_source_name(self):
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return "{} (v{}) {}".format(self.source_form.default_name(), self.app.version, today)


class CaseDataSourceHelper(ManagedReportBuilderDataSourceHelper):
    """
    A ReportBuilderDataSourceInterface specifically for when source_type = 'case'.
    """

    @property
    def source_doc_type(self):
        return 'CommCareCase'

    @property
    @memoized
    def filter(self):
        return make_case_data_source_filter(self.source_id)

    def base_item_expression(self, is_multiselect_chart_report, multiselect_field=None):
        assert not is_multiselect_chart_report
        return {}

    @property
    @memoized
    def data_source_properties(self):
        property_map = {
            'closed': _('Case Closed'),
            'user_id': _('User ID Last Updating Case'),
            'owner_name': _('Case Owner'),
            'mobile worker': _('Mobile Worker Last Updating Case'),
            'case_id': _('Case ID')
        }

        properties = OrderedDict()
        for property in self.case_properties:
            if property in DEFAULT_CASE_PROPERTY_DATATYPES:
                data_types = DEFAULT_CASE_PROPERTY_DATATYPES[property]
            else:
                data_types = ["string", "decimal", "datetime"]

            properties[property] = DataSourceProperty(
                type=PROPERTY_TYPE_CASE_PROP,
                id=property,
                text=property_map.get(property, property.replace('_', ' ')),
                source=property,
                data_types=data_types,
            )
        properties[COMPUTED_OWNER_NAME_PROPERTY_ID] = self._get_owner_name_pseudo_property()
        properties[COMPUTED_USER_NAME_PROPERTY_ID] = self._get_user_name_pseudo_property()

        if SHOW_IDS_IN_REPORT_BUILDER.enabled(self.domain):
            properties['case_id'] = self._get_case_id_pseudo_property()

        if SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE.enabled(self.domain):
            properties[COMPUTED_OWNER_LOCATION_PROPERTY_ID] = self._get_owner_location_pseudo_property()
            properties[COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID] = \
                self._get_owner_location_with_descendants_pseudo_property()
            properties[COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID] = \
                self._get_owner_location_archived_with_descendants_pseudo_property()

        return properties

    @staticmethod
    def _get_case_id_pseudo_property():
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id='case_id',
            text=_('Case ID'),
            source='case_id',
            data_types=["string"],
        )

    @staticmethod
    def _get_owner_name_pseudo_property():
        # owner_name is a special pseudo-case property for which
        # the report builder will create a related_doc indicator based
        # on the owner_id of the case.
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_OWNER_NAME_PROPERTY_ID,
            text=_('Case Owner'),
            source=COMPUTED_OWNER_NAME_PROPERTY_ID,
            data_types=["string"],
        )

    @classmethod
    def _get_owner_location_pseudo_property(cls):
        # owner_location is a special pseudo-case property for which
        # the report builder reference the owner_id, but treat it as a location
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_OWNER_LOCATION_PROPERTY_ID,
            text=_('Case Owner (Location)'),
            source=COMPUTED_OWNER_LOCATION_PROPERTY_ID,
            data_types=["string"],
        )

    @classmethod
    def _get_owner_location_with_descendants_pseudo_property(cls):
        # similar to the location property but also include descendants
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
            text=_('Case Owner (Location w/ Descendants)'),
            source=COMPUTED_OWNER_LOCATION_WITH_DESENDANTS_PROPERTY_ID,
            data_types=["string"],
        )

    @classmethod
    def _get_owner_location_archived_with_descendants_pseudo_property(cls):
        # similar to the location property but also include descendants
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID,
            text=_('Case Owner (Location w/ Descendants and Archived Locations)'),
            source=COMPUTED_OWNER_LOCATION_ARCHIVED_WITH_DESCENDANTS_PROPERTY_ID,
            data_types=["string"],
        )

    @staticmethod
    def _get_user_name_pseudo_property():
        # user_name is a special pseudo case property for which
        # the report builder will create a related_doc indicator based on the
        # user_id of the case
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_USER_NAME_PROPERTY_ID,
            text=_('Mobile Worker Last Updating Case'),
            source=COMPUTED_USER_NAME_PROPERTY_ID,
            data_types=["string"],
        )


class ApplicationCaseDataSourceHelper(CaseDataSourceHelper):
    def __init__(self, domain, app, source_type, source_id):
        self.app = app
        assert source_type == 'case'
        super().__init__(domain, source_type, source_id)
        prop_map = get_case_properties(
            self.app, [self.source_id], defaults=list(DEFAULT_CASE_PROPERTY_DATATYPES),
            include_parent_properties=True,
        )
        self.case_properties = sorted(set(prop_map[self.source_id]) | {'closed', 'closed_on'})

    def _get_data_source_build_information(self):
        return DataSourceBuildInformation(
            source_id=self.source_id,
            app_id=self.app._id,
            app_version=self.app.version,
        )

    @property
    def uses_registry_data_source(self):
        return False

    @property
    @memoized
    def data_source_name(self):
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return "{} (v{}) {}".format(self.source_id, self.app.version, today)


class RegistryCaseDataSourceHelper(CaseDataSourceHelper):
    def __init__(self, domain, registry_slug, source_type, source_id):
        assert source_type == 'case'
        self.registry_slug = registry_slug
        super().__init__(domain, source_type, source_id)

        registry_helper = DataRegistryHelper(self.domain, registry_slug=self.registry_slug)
        owning_domain = registry_helper.registry.domain
        prop_map = get_data_dict_props_by_case_type(owning_domain)
        self.case_properties = sorted(
            set(prop_map[self.source_id]) | {'closed', 'closed_on'}
        )

    def _get_data_source_build_information(self):
        return DataSourceBuildInformation(
            source_id=self.source_id,
            registry_slug=self.registry_slug,
        )

    @property
    def uses_registry_data_source(self):
        return True

    @property
    @memoized
    def data_source_name(self):
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return "{} {} {}".format(self.source_id, self.registry_slug, today)

    @property
    def data_source_properties(self):
        properties = super().data_source_properties
        properties[COMMCARE_PROJECT] = DataSourceProperty(
            type=PROPERTY_TYPE_RAW,
            id=COMMCARE_PROJECT,
            text=_('CommCare Project'),
            source='commcare_project',
            data_types=["string"],
        )
        return properties

    def construct_data_source(self, table_id, **kwargs):
        return RegistryDataSourceConfiguration(
            domain=self.domain,
            table_id=table_id,
            registry_slug=self.registry_slug,
            **kwargs
        )

    def _get_datasource_default_columns(self):
        return {
            column.id
            for indicator in RegistryDataSourceConfiguration().default_indicators
            for column in indicator.get_columns()
        }


def get_data_source_interface(domain, app, source_type, source_id, registry_slug):
    if registry_slug is not None and source_type == DATA_SOURCE_TYPE_CASE:
        return RegistryCaseDataSourceHelper(domain, registry_slug, source_type, source_id)
    if source_type in APP_DATA_SOURCE_TYPE_VALUES:
        helper = {
            DATA_SOURCE_TYPE_CASE: ApplicationCaseDataSourceHelper,
            DATA_SOURCE_TYPE_FORM: ApplicationFormDataSourceHelper
        }[source_type]
        return helper(domain, app, source_type, source_id)
    else:
        return UnmanagedDataSourceHelper(domain, app, source_type, source_id)


class DataSourceForm(forms.Form):
    report_name = forms.CharField()

    def __init__(self, domain, max_allowed_reports, request_user, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.max_allowed_reports = max_allowed_reports
        self.request_user = request_user

        self.registry_permission_checker = RegistryPermissionCheck(self.domain, self.request_user)
        # TODO: Map reports.
        self.app_source_helper = ApplicationDataSourceUIHelper(
            enable_raw=SHOW_RAW_DATA_SOURCES_IN_REPORT_BUILDER.enabled(self.domain),
            enable_registry=(DATA_REGISTRY_UCR.enabled(self.domain)
                             and self.registry_permission_checker.can_view_some_data_registry_contents()),
            registry_permission_checker=self.registry_permission_checker
        )
        self.app_source_helper.bootstrap(self.domain)
        self.fields.update(self.app_source_helper.get_fields())

        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.form_id = "report-builder-form"
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Report'),
                hqcrispy.FieldWithHelpBubble(
                    'report_name',
                    help_bubble_text=_(
                        'Web users will see this name in the "Reports" section of CommCareHQ and can click to '
                        'view the report'
                    )
                )
            ),
            self.get_data_layout(),
            hqcrispy.FormActions(
                StrictButton(
                    _('Next'),
                    type="submit",
                    css_id='js-next-data-source',
                    css_class="btn-primary",
                )
            ),
        )

    def get_data_layout(self):
        if not (DATA_REGISTRY_UCR.enabled(self.domain)
                and self.registry_permission_checker.can_view_some_data_registry_contents()):
            return crispy.Fieldset(
                _('Data'), *self.app_source_helper.get_crispy_fields(),
            )
        else:
            help_texts = self.app_source_helper.get_crispy_filed_help_texts()
            return crispy.Fieldset(
                _('Data'),
                hqcrispy.FieldWithHelpBubble('source_type', help_bubble_text=help_texts['source_type']),
                crispy.Div(
                    crispy.HTML('<input type="radio" name="project_data" id="one_project" '
                                'value="isDataFromOneProject" data-bind="checked: isDataFromOneProject,'
                                ' checkedValue: \'true\'" class="project_data-option"/>'
                                '<label for="one_project" class="project_data-label">%s</label>'
                                % _("Data From My Project Space")),
                    crispy.Div(
                        hqcrispy.FieldWithHelpBubble('application', help_bubble_text=help_texts['application']),
                        style="padding-left: 50px;"
                    ),
                    crispy.HTML('<input type="radio" name="project_data" id="many_projects" '
                                'value="isDataFromOneProject" data-bind="checked: isDataFromOneProject, '
                                'checkedValue: \'false\'" class="project_data-option"/><label '
                                'for="many_projects" class="project_data-label">%s</label>'
                                % _("Data From My Project Space And Others")),
                    crispy.Div(
                        hqcrispy.FieldWithHelpBubble(
                            'registry_slug',
                            help_bubble_text=help_texts['registry_slug']
                        ),
                        style="padding-left: 50px;"
                    ),
                ),
                hqcrispy.FieldWithHelpBubble('source', help_bubble_text=help_texts['source']),
            )

    @property
    def sources_map(self):
        return self.app_source_helper.all_sources

    @property
    def dropdown_map(self):
        return self.app_source_helper.app_and_registry_sources

    def get_selected_source(self):
        return self.app_source_helper.get_app_source(self.cleaned_data)

    def clean(self):
        """
        Raise a validation error if there are already 5 data sources and this
        report won't be able to use one of the existing ones.
        """
        cleaned_data = super(DataSourceForm, self).clean()

        existing_reports = get_report_and_registry_report_configs_for_domain(self.domain)
        builder_reports = [report for report in existing_reports if report.report_meta.created_by_builder]
        if has_report_builder_access(self.domain) and len(builder_reports) >= self.max_allowed_reports:
            # Don't show the warning when domain does not have report buidler access, because this is just a
            # preview and the report will not be saved.
            raise forms.ValidationError(_(
                "Too many reports!\n"
                "Creating this report would cause you to go over the maximum "
                "number of report builder reports allowed in this domain. Your "
                "limit is {number}. "
                "To continue, delete another report and try again. "
            ).format(number=self.max_allowed_reports))

        return cleaned_data


_shared_properties = ['exists_in_current_version', 'display_text', 'property', 'data_source_field']
UserFilterViewModel = namedtuple("UserFilterViewModel", _shared_properties + ['format'])
DefaultFilterViewModel = namedtuple("DefaultFilterViewModel",
                                    _shared_properties + ['format', 'pre_value', 'pre_operator'])
ColumnViewModel = namedtuple("ColumnViewModel", _shared_properties + ['calculation'])


class ConfigureNewReportBase(forms.Form):
    user_filters = FilterField(required=False)
    default_filters = FilterField(required=False)
    report_title = forms.CharField(widget=forms.HiddenInput, required=False)
    report_description = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, domain, report_name, app_id, source_type, report_source_id, existing_report=None,
                 registry_slug=None,
                 *args, **kwargs):
        """
        This form can be used to create a new ReportConfiguration, or to modify
        an existing one if existing_report is set.
        """
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)
        self.existing_report = existing_report
        self.domain = domain

        if self.existing_report:
            self._bootstrap(self.existing_report)
        else:
            self.registry_slug = registry_slug
            self.report_name = report_name
            assert source_type in REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES
            self.source_type = source_type
            self.report_source_id = report_source_id
            self.app = Application.get(app_id) if app_id else None
            if self.app:
                assert self.domain == self.app.domain

        self.ds_builder = get_data_source_interface(
            self.domain, self.app, self.source_type, self.report_source_id, self.registry_slug
        )
        self.report_column_options = self.ds_builder.report_column_options

        self.data_source_properties = self.ds_builder.data_source_properties

        self._report_columns_by_column_id = {}
        for column in self.report_column_options.values():
            for agg in column.aggregation_options:
                indicators = column.get_indicators(agg)
                for i in indicators:
                    self._report_columns_by_column_id[i['column_id']] = column

    def _bootstrap(self, existing_report):
        """
        Use an existing report to initialize some of the instance variables of this
        form. This method is used when editing an existing report.
        """
        self.report_name = existing_report.title

        self.source_type = get_source_type_from_report_config(existing_report)
        assert self.domain == existing_report.domain
        if self.source_type in APP_DATA_SOURCE_TYPE_VALUES:
            self.report_source_id = existing_report.config.meta.build.source_id
            app_id = existing_report.config.meta.build.app_id
            self.registry_slug = existing_report.config.meta.build.registry_slug
            self.app = None
            if app_id:
                self.app = Application.get(app_id)
            elif not self.registry_slug:
                raise BadBuilderConfigError(DATA_SOURCE_MISSING_APP_ERROR_MESSAGE)
        else:
            assert self.source_type == DATA_SOURCE_TYPE_RAW
            self.report_source_id = existing_report.config_id
            self.app = self.registry_slug = None

    @property
    def _configured_columns(self):
        """
        To be used by ManagedReportBuilderDataSourceHelper.indicators()
        """
        configured_columns = self.cleaned_data['columns']
        location = self.cleaned_data.get("location")
        if location and all(location != c.get('property')
                            for c in configured_columns):
            configured_columns += [{
                "property": location,
                "calculation": UI_AGG_GROUP_BY  # Not aggregated
            }]
        return configured_columns

    def _get_data_source_configuration_kwargs(self):
        filters = self.cleaned_data['user_filters'] + self.cleaned_data['default_filters']
        ms_field = self._report_aggregation_cols[0] if self._is_multiselect_chart_report else None
        return self.ds_builder.get_datasource_constructor_kwargs(self._configured_columns,
                                                                 filters,
                                                                 self._is_multiselect_chart_report,
                                                                 ms_field)

    def _build_data_source(self):
        data_source_config = self.ds_builder.construct_data_source(
            # The uuid gets truncated, so it's not really universally unique.
            table_id=clean_table_name(self.domain, str(uuid.uuid4().hex)),
            **self._get_data_source_configuration_kwargs()
        )
        data_source_config.validate()
        data_source_config.save()
        tasks.rebuild_indicators.delay(data_source_config._id, source="report_builder",
                                       domain=data_source_config.domain)
        return data_source_config._id

    def update_report(self):
        self._update_data_source_if_necessary()
        self.existing_report.aggregation_columns = self._report_aggregation_cols
        self.existing_report.columns = self._get_report_columns()
        self.existing_report.filters = self._report_filters
        self.existing_report.configured_charts = self._report_charts
        self.existing_report.title = self.cleaned_data['report_title'] or _("Report Builder Report")
        self.existing_report.description = self.cleaned_data['report_description']
        self.existing_report.validate()
        self.existing_report.save()

        DomainAuditRecordEntry.update_calculations(self.domain, 'cp_n_reports_edited')

        return self.existing_report

    def _update_data_source_if_necessary(self):
        if self.ds_builder.uses_managed_data_source:
            data_source = get_ucr_datasource_config_by_id(self.existing_report.config_id)
            if data_source.get_report_count() > 1:
                # If another report is pointing at this data source, create a new
                # data source for this report so that we can change the indicators
                # without worrying about breaking another report.
                data_source_config_id = self._build_data_source()
                self.existing_report.config_id = data_source_config_id
            else:
                indicators = self.ds_builder.indicators(
                    self._configured_columns,
                    self.cleaned_data['user_filters'] + self.cleaned_data['default_filters'],
                )
                if data_source.configured_indicators != indicators:
                    for property_name, value in self._get_data_source_configuration_kwargs().items():
                        setattr(data_source, property_name, value)
                    data_source.save()
                    now = datetime.datetime.utcnow()
                    tasks.rebuild_indicators.delay(
                        data_source._id, source='report_builder_update',
                        trigger_time=now, domain=data_source.domain
                    )

    def create_report(self):
        """
        Creates data source and report config.

        :raises BadSpecError if validation fails when building data source, or report is invalid
        """
        if self.ds_builder.uses_managed_data_source:
            data_source_config_id = self._build_data_source()
        else:
            data_source_config_id = self.ds_builder.data_source_id
        report = self.ds_builder.report_config_class(
            domain=self.domain,
            config_id=data_source_config_id,
            title=self.cleaned_data['report_title'] or self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._get_report_columns(),
            filters=self._report_filters,
            configured_charts=self._report_charts,
            description=self.cleaned_data['report_description'],
            report_meta=ReportMeta(
                created_by_builder=True,
                report_builder_version="2.0",
                builder_report_type=self.report_type,
                builder_source_type=self.source_type,
            )
        )
        report.validate()

        DomainAuditRecordEntry.update_calculations(self.domain, 'cp_n_reports_created')

        report.save()
        return report

    def create_temp_report(self, data_source_id, username):
        """
        Updates the datasource then creates and saves a report config.

        :raises BadSpecError if report is invalid
        """

        self._update_temp_datasource(data_source_id, username)
        report = self.ds_builder.report_config_class(
            domain=self.domain,
            config_id=data_source_id,
            title=self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._get_report_columns(),
            filters=self._report_filters,
            configured_charts=self._report_charts,
            data_source_type=guess_data_source_type(data_source_id),
            report_meta=ReportMeta(
                created_by_builder=True,
                report_builder_version="2.0",
                builder_report_type=self.report_type
            )
        )
        report.validate()
        report.save()
        return report

    def create_temp_data_source_if_necessary(self, username):
        """
        Build a temp datasource and return the ID
        """
        if not self.ds_builder.uses_managed_data_source:
            # if the data source interface doens't use a temp data source then the id is just the source_id
            return self.ds_builder.data_source_id

        filters = [f._asdict() for f in self.initial_user_filters + self.initial_default_filters]
        columns = [c._asdict() for c in self.initial_columns]

        data_source_config = self.ds_builder.construct_data_source(
            table_id=clean_table_name(self.domain, uuid.uuid4().hex),
            **self.ds_builder.get_temp_datasource_constructor_kwargs(columns, filters)
        )
        data_source_config.validate()
        data_source_config.save()

        # expire the data source
        always_eager = hasattr(settings, "CELERY_TASK_ALWAYS_EAGER") and settings.CELERY_TASK_ALWAYS_EAGER
        # CELERY_TASK_ALWAYS_EAGER will cause the data source to be deleted immediately. Switch it off temporarily
        settings.CELERY_TASK_ALWAYS_EAGER = False
        tasks.delete_data_source_task.apply_async(
            (self.domain, data_source_config._id),
            countdown=TEMP_DATA_SOURCE_LIFESPAN
        )
        settings.CELERY_TASK_ALWAYS_EAGER = always_eager

        tasks.rebuild_indicators(data_source_config._id,
                                 username,
                                 limit=SAMPLE_DATA_MAX_ROWS)  # Do synchronously
        self._filter_data_source_changes(data_source_config._id)
        return data_source_config._id

    @staticmethod
    def _filter_data_source_changes(data_source_config_id):
        """
        Add filter to data source to prevent it from being updated by DB changes
        """
        # Reload using the ID instead of just passing in the object to avoid ResourceConflicts
        data_source_config = get_ucr_datasource_config_by_id(data_source_config_id)
        data_source_config.configured_filter = {
            # An expression that is always false:
            "type": "boolean_expression",
            "operator": "eq",
            "expression": 1,
            "property_value": 2,
        }
        data_source_config.validate()
        data_source_config.save()

    def _update_temp_datasource(self, data_source_config_id, username):
        if not self.ds_builder.uses_managed_data_source:
            return

        data_source_config = get_ucr_datasource_config_by_id(data_source_config_id, allow_deleted=True)
        if data_source_config.is_deleted:
            # undelete the temp data source
            undo_delete(data_source_config, save=False)

        filters = self.cleaned_data['user_filters'] + self.cleaned_data['default_filters']
        # The data source needs indicators for all possible calculations, not just the ones currently in use
        required_columns = {c["column_id"]
                            for c in self.ds_builder.all_possible_indicators(self._configured_columns, filters)}
        current_columns = {c["column_id"] for c in data_source_config.configured_indicators}
        missing_columns = required_columns - current_columns

        # rebuild the table
        if missing_columns:
            temp_config = self.ds_builder.get_temp_datasource_constructor_kwargs(self._configured_columns, filters)
            data_source_config.configured_indicators = temp_config["configured_indicators"]
            data_source_config.configured_filter = temp_config["configured_filter"]
            data_source_config.base_item_expression = temp_config["base_item_expression"]
            data_source_config.validate()
            data_source_config.save()
            tasks.rebuild_indicators(data_source_config._id,
                                     username,
                                     limit=SAMPLE_DATA_MAX_ROWS)  # Do synchronously
            self._filter_data_source_changes(data_source_config._id)

    @property
    @memoized
    def initial_default_filters(self):
        return [self._get_view_model(f) for f in self.existing_report.prefilters] if self.existing_report else []

    @property
    @memoized
    def initial_user_filters(self):
        if self.existing_report:
            return [self._get_view_model(f) for f in self.existing_report.filters_without_prefilters]
        if self.source_type == 'case':
            return self._default_case_report_filters
        elif self.source_type == 'form':
            return self._default_form_report_filters
        else:
            return []

    @property
    @memoized
    def _default_case_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='closed',
                data_source_field=None,
                display_text=_('Closed'),
                format='Choice',
            ),
            UserFilterViewModel(
                exists_in_current_version=True,
                property=COMPUTED_OWNER_NAME_PROPERTY_ID,
                data_source_field=None,
                display_text=_('Case Owner'),
                format='Choice',
            ),
        ]

    @property
    @memoized
    def _default_form_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='timeEnd',
                data_source_field=None,
                display_text='Form completion time',
                format=const.FORMAT_DATE,
            ),
        ]

    def _get_view_model(self, filter):
        """
        Given a filter_spec, return a FilterViewModel representing
        the knockout view model representing this filter in the report builder.

        """
        field = filter['field']
        field, exists = self._check_and_update_column(field)
        if filter['type'] == 'pre':
            return self._get_default_filter_view_model_from_pre_filter(field, filter, exists)
        else:
            filter_type_map = {
                'dynamic_choice_list': const.FORMAT_CHOICE,
                # This exists to handle the `closed` filter that might exist
                'choice_list': const.FORMAT_CHOICE,
                'date': const.FORMAT_DATE,
                'numeric': const.FORMAT_NUMERIC
            }
            try:
                format_ = filter_type_map[filter['type']]
            except KeyError:
                raise BadBuilderConfigError(_(
                    "This report references the '{}' filter, which is not compatible with "
                    "the Report Builder. It is only editable in the advanced interface."
                ).format(filter['type']))
            return UserFilterViewModel(
                exists_in_current_version=exists,
                display_text=filter['display'],
                format=format_,
                property=self._get_property_id_by_indicator_id(field) if exists else None,
                data_source_field=field if not exists else None
            )

    def _get_default_filter_view_model_from_pre_filter(self, field, pre_filter, exists):
        return DefaultFilterViewModel(
            exists_in_current_version=exists,
            display_text='',
            format=get_pre_filter_format(pre_filter),
            property=self._get_property_id_by_indicator_id(field) if exists else None,
            data_source_field=field if not exists else None,
            pre_value=pre_filter['pre_value'],
            pre_operator=pre_filter['pre_operator'],
        )

    def _get_column_option_by_indicator_id(self, indicator_column_id):
        """
        Return the ColumnOption corresponding to the given indicator id.
        NOTE: This currently assumes that there is a one-to-one mapping between
        ColumnOptions and data source indicators, but we may want to remove
        this assumption as we add functionality to the report builder.
        :param indicator_column_id: The column_id field of a data source
            indicator configuration.
        :return: The corresponding ColumnOption
        """
        return self._report_columns_by_column_id[indicator_column_id]

    def _get_property_id_by_indicator_id(self, indicator_column_id):
        """
        Return the data source property id corresponding to the given data
        source indicator column id.
        :param indicator_column_id: The column_id field of a data source indicator
            configuration dictionary
        :return: A DataSourceProperty property id, e.g. "/data/question1"
        """
        column = self._report_columns_by_column_id.get(indicator_column_id)
        if column:
            return column.get_property()

    def _check_and_update_column(self, column_id):
        """
        :param column_id: a string like "data_date_q_d1b3693e"

        :return: (column_id, exists) tuple where:

            column_id is the valid column id. If the column is from version 1
            of the report builder, it will be converted to the current version.

            exists = True if column corresponds to a question/case property in
            the current version of this form/case configuration. May be False
            if the user makes a report, modifies the app, then edits the report.
        """
        if column_id in self._report_columns_by_column_id:
            return column_id, True

        # This is needed because previously hidden value questions and case
        # property columns didn't have a datatype in their ids, but the builder
        # now expects that, so this attempts to just append a datatype.
        possibly_corrected_column_id = column_id + "_string"
        if possibly_corrected_column_id in self._report_columns_by_column_id:
            return possibly_corrected_column_id, True

        return column_id, False

    def _get_multiselect_indicator_id(self, column_field, indicators):
        """
        If this column_field corresponds to a multiselect data source indicator, then return the id of the
        indicator. Otherwise return None.
        :param column_field: The "field" property of a report column
        :return: a data source indicator id
        """
        for indicator in indicators:
            if column_field.startswith(indicator['column_id']) and indicator['type'] == 'choice_list':
                return indicator['column_id']
        return None

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']

    def _get_report_columns(self):
        """
        Columns to be passed to the ReportConfiguration object.
        You can add additional transformations that should apply to all report types here.
        """
        columns = self._report_columns
        if OVERRIDE_EXPANDED_COLUMN_LIMIT_IN_REPORT_BUILDER.enabled(self.domain):
            for column in columns:
                if column['aggregation'] == UCR_AGG_EXPAND:
                    column['max_expansion'] = LENIENT_MAXIMUM_EXPANSION
        return columns

    @property
    def _report_columns(self):
        """
        Returns column dicts for columns posted from the UI
        """
        return []

    @property
    def _is_multiselect_chart_report(self):
        return False

    @property
    def _report_filters(self):
        """
        Return the dict filter configurations to be used by the
        ReportConfiguration that this form produces.
        """

        def _make_report_filter(conf, index):
            property = self.data_source_properties[conf["property"]]
            return property.to_report_filter(conf, index)

        user_filter_configs = self.cleaned_data['user_filters']
        default_filter_configs = self.cleaned_data['default_filters']
        filters = [_make_report_filter(f, i) for i, f in enumerate(user_filter_configs + default_filter_configs)]
        if self.source_type == 'case':
            # The UI doesn't support specifying "choice_list" filters, only "dynamic_choice_list" filters.
            # But, we want to make the open/closed filter a cleaner "choice_list" filter, so we do that here.
            self._convert_closed_filter_to_choice_list(filters)
        return filters

    @classmethod
    def _convert_closed_filter_to_choice_list(cls, filters):
        for f in filters:
            if f['field'] == get_column_name('closed') and f['type'] == 'dynamic_choice_list':
                f['type'] = 'choice_list'
                f['choices'] = [
                    {'value': 'True'},
                    {'value': 'False'}
                ]

    @property
    def _report_charts(self):
        return []


class ConfigureListReportForm(ConfigureNewReportBase):
    report_type = 'list'
    columns = JsonField(
        expected_type=list,
        null_values=([],),
        required=False,
        widget=forms.HiddenInput,
    )

    @property
    @memoized
    def initial_columns(self):
        if self.existing_report:
            reverse_agg_map = {
                UCR_AGG_SIMPLE: UI_AGG_GROUP_BY,
                UCR_AGG_AVG: UI_AGG_AVERAGE,
                UCR_AGG_SUM: UI_AGG_SUM,
                UCR_AGG_EXPAND: UI_AGG_COUNT_PER_CHOICE,
            }
            added_multiselect_columns = set()
            cols = []
            for c in self.existing_report.columns:
                mselect_indicator_id = self._get_multiselect_indicator_id(
                    c['field'], self.existing_report.config.configured_indicators
                )
                indicator_id = mselect_indicator_id or c['field']
                display = c['display']
                agg = c.get("aggregation")
                indicator_id, exists = self._check_and_update_column(indicator_id)

                if mselect_indicator_id:
                    if mselect_indicator_id not in added_multiselect_columns:
                        added_multiselect_columns.add(mselect_indicator_id)
                        display = MultiselectQuestionColumnOption.LABEL_DIVIDER.join(
                            display.split(MultiselectQuestionColumnOption.LABEL_DIVIDER)[:-1]
                        )
                        agg = UI_AGG_COUNT_PER_CHOICE
                    else:
                        continue

                cols.append(
                    ColumnViewModel(
                        display_text=display,
                        exists_in_current_version=exists,
                        property=(
                            self._get_column_option_by_indicator_id(indicator_id).get_property()
                            if exists else None
                        ),
                        data_source_field=indicator_id if not exists else None,
                        calculation=reverse_agg_map.get(agg, UI_AGG_COUNT_PER_CHOICE)
                    )
                )
            return cols
        else:
            return self._get_default_columns()

    def _get_default_columns(self):
        if self.source_type == "case":
            return self._get_default_case_report_columns()
        elif self.source_type == "form":
            return self._get_default_form_report_columns()
        else:
            return self._get_default_raw_report_columns()

    def _get_default_case_report_columns(self):
        cols = []
        cols.append(ColumnViewModel(
            display_text="Name",
            exists_in_current_version=True,
            property="name",
            data_source_field=(
                self.data_source_properties['name']
                .to_report_column_option()
                .get_indicators(UI_AGG_COUNT_PER_CHOICE)[0]['column_id']),
            calculation=UI_AGG_COUNT_PER_CHOICE
        ))
        cols.append(ColumnViewModel(
            display_text="Owner",
            exists_in_current_version=True,
            property=COMPUTED_OWNER_NAME_PROPERTY_ID,
            data_source_field=(
                self.data_source_properties[COMPUTED_OWNER_NAME_PROPERTY_ID]
                .to_report_column_option()
                .get_indicators(UI_AGG_COUNT_PER_CHOICE)[0]['column_id']),
            calculation=UI_AGG_COUNT_PER_CHOICE
        ))
        case_props_found = 0

        skip_list = set([COMPUTED_OWNER_NAME_PROPERTY_ID, COMPUTED_USER_NAME_PROPERTY_ID] + STATIC_CASE_PROPS)
        for prop in self.data_source_properties.values():
            if prop.get_type() == PROPERTY_TYPE_CASE_PROP and prop.get_id() not in skip_list:
                case_props_found += 1
                cols.append(ColumnViewModel(
                    display_text=prop.get_text(),
                    exists_in_current_version=True,
                    property=prop.get_id(),
                    data_source_field=(
                        prop.to_report_column_option()
                        .get_indicators(UI_AGG_COUNT_PER_CHOICE)[0]['column_id']),
                    calculation=UI_AGG_COUNT_PER_CHOICE,
                ))
                if case_props_found == 3:
                    break
        return cols

    def _get_default_form_report_columns(self):
        cols = []
        prop = self.data_source_properties['username']
        cols.append(ColumnViewModel(
            display_text=prop.get_text(),
            exists_in_current_version=True,
            property=prop.get_id(),
            data_source_field=(
                prop.to_report_column_option()
                .get_indicators(UI_AGG_COUNT_PER_CHOICE)[0]['column_id']),
            calculation=UI_AGG_COUNT_PER_CHOICE
        ))
        questions = [p for p in self.data_source_properties.values()
                     if p.get_type() == PROPERTY_TYPE_QUESTION]
        if len(questions) > 9:
            questions = questions[:9]
        for q in questions:
            cols.append(ColumnViewModel(
                display_text=q.get_text(),
                exists_in_current_version=True,
                property=q.get_id(),
                data_source_field=q.get_id(),
                calculation=UI_AGG_COUNT_PER_CHOICE,
            ))
        return cols

    def _get_default_raw_report_columns(self):
        cols = []
        # just grab the first five columns that aren't system fields
        # eventually this should be reconciled with data dictionary / system_properties.py
        props_to_use = [
            p for p in self.data_source_properties.values()
            if p.get_id() not in ('doc_id', 'inserted_at')
        ]
        for prop in props_to_use[:5]:
            cols.append(ColumnViewModel(
                display_text=prop.get_text(),
                exists_in_current_version=True,
                property=prop.get_id(),
                data_source_field=(
                    prop.to_report_column_option()
                    .get_indicators(UI_AGG_COUNT_PER_CHOICE)[0]['column_id']),
                calculation=UI_AGG_COUNT_PER_CHOICE,
            ))
        return cols

    @property
    def _report_columns(self):
        return self._build_report_columns(
            ui_aggregation_override=UI_AGG_GROUP_BY, is_aggregated_on_override=False
        )

    def _build_report_columns(self, ui_aggregation_override=None, is_aggregated_on_override=None):
        columns = []
        for i, conf in enumerate(self.cleaned_data['columns']):
            ui_aggregation = conf['calculation'] if ui_aggregation_override is None else ui_aggregation_override
            is_aggregated_on = is_aggregated_on_override
            if is_aggregated_on_override is None:
                is_aggregated_on = conf.get('calculation') == UI_AGG_GROUP_BY
            columns.extend(
                self.ds_builder.report_column_options[conf['property']].to_column_dicts(
                    index=i,
                    display_text=conf.get('display_text', conf['property']),
                    ui_aggregation=ui_aggregation,
                    is_aggregated_on=is_aggregated_on,
                )
            )
        return columns

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']


class ConfigureTableReportForm(ConfigureListReportForm):
    report_type = 'table'
    chart = forms.CharField(widget=forms.HiddenInput)

    @property
    def _report_charts(self):

        non_agged_columns = [c for c in self._report_columns if c['aggregation'] != UCR_AGG_SIMPLE]
        agged_columns = [c for c in self._report_columns if c['aggregation'] == UCR_AGG_SIMPLE]

        if non_agged_columns:
            if self.cleaned_data['chart'] == "bar":
                return [{
                    "type": "multibar",
                    "x_axis_column": agged_columns[0]['column_id'] if agged_columns else '',
                    # Populate only the top level columns here.
                    # During chart render all possible columns for the chart are fetched based on records in DB
                    # checkout ReportConfiguration.charts
                    "y_axis_columns": [
                        {"column_id": c["column_id"], "display": c["display"]} for c in non_agged_columns
                    ],
                }]
            elif self.cleaned_data['chart'] == "pie":
                if not agged_columns:
                    raise BadBuilderConfigError(_(
                        'You must have at least one group by column to use pie charts!'
                    ))
                return [{
                    "type": "pie",
                    "aggregation_column": agged_columns[0]['column_id'],
                    "value_column": non_agged_columns[0]['column_id'],
                }]
        return []

    @property
    def _is_multiselect_chart_report(self):
        """
        Return True if this is a chart report aggregated by a multiselect question.
        The data sources for these sorts of reports are handled differently than other reports.
        """
        # Disabling this feature for now
        return False
        # if self.cleaned_data['chart'] in ("pie", "bar"):
        #     agg_property = self.data_source_properties[self.cleaned_data['group_by'][0]]
        #     return agg_property.type == "question" and agg_property.source['type'] == "MSelect"
        # return False

    @property
    def _report_columns(self):
        return self._build_report_columns()

    @property
    @memoized
    def _report_aggregation_cols(self):
        return [
            self.ds_builder.report_column_options[conf['property']].get_indicators(UI_AGG_GROUP_BY)[0]['column_id']
            for conf in self.cleaned_data['columns'] if conf['calculation'] == UI_AGG_GROUP_BY
        ]


class ConfigureMapReportForm(ConfigureListReportForm):
    report_type = 'map'
    location = forms.ChoiceField(label="Location field", required=False)

    def __init__(self, domain, report_name, app_id, source_type, report_source_id, existing_report=None,
                 *args, **kwargs):
        super(ConfigureMapReportForm, self).__init__(
            domain, report_name, app_id, source_type, report_source_id, existing_report, *args, **kwargs
        )
        self.fields['location'].choices = self._location_choices

        # Set initial value of location
        if self.existing_report and existing_report.location_column_id:
            existing_loc_col = existing_report.location_column_id
            self.fields['location'].initial = self._get_property_id_by_indicator_id(existing_loc_col)

    @property
    def _location_choices(self):
        return [(p.get_id(), p.get_text()) for p in self.data_source_properties.values()]

    @property
    @memoized
    def initial_columns(self):
        columns = super(ConfigureMapReportForm, self).initial_columns

        # Remove the location indicator from the columns.
        # It gets removed because we want it to be a column in the report,
        # but we don't want it to appear in the builder.
        if self.existing_report and self.existing_report.location_column_id:
            col_id = self.existing_report.location_column_id
            location_property = self._get_property_id_by_indicator_id(col_id)
            return [c for c in columns if c.property != location_property]
        return columns

    @property
    def location_field(self):
        return self.cleaned_data["location"]

    @property
    def _report_columns(self):
        columns = super(ConfigureMapReportForm, self)._report_columns

        if self.location_field:
            loc_column = self.data_source_properties[self.location_field].to_report_column_option()
            loc_field_id = loc_column.get_indicators(UI_AGG_GROUP_BY)[0]['column_id']
            loc_field_text = loc_column.get_default_display()

            displaying_loc_column = False
            for c in columns:
                if c['field'] == loc_field_id:
                    c['type'] = "location"
                    displaying_loc_column = True
                    break

            # Add the location indicator to the columns if it's not already present.
            if not displaying_loc_column:
                columns = columns + [{
                    "column_id": loc_field_id,
                    "type": "location",
                    'field': loc_field_id,
                    'display': loc_field_text
                }]

        return columns
