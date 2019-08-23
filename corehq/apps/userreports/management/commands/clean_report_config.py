
from collections import OrderedDict
from copy import deepcopy
from io import open
import simplejson as json
import six
import textwrap

from django.core.management.base import BaseCommand

from corehq.apps.userreports.models import ReportConfiguration, StaticReportConfiguration
from corehq.apps.userreports.reports.filters import specs
from six.moves import zip

COLUMN_PARAMS_ORDER = [
    'comment',
    'display',
    'column_id',
    'description',
    'type',
    'field',
    'numerator',
    'denominator',
    'expression',
    'format',
    'aggregation',
    'calculate_total',
    'visible',
    'transform',
    # Anything not listed here will appear last, in alphabetical order
]
FILTER_SPECS = {
    'date': specs.DateFilterSpec,
    'quarter': specs.QuarterFilterSpec,
    'pre': specs.PreFilterSpec,
    'choice_list': specs.ChoiceListFilterSpec,
    'dynamic_choice_list': specs.DynamicChoiceListFilterSpec,
    'multi_field_dynamic_choice_list': specs.MultiFieldDynamicChoiceFilterSpec,
    'numeric': specs.NumericFilterSpec,
    'location_drilldown': specs.LocationDrilldownFilterSpec,
}
FILTER_PARAMS_ORDER = [
    'comment',
    'display',
    'slug',
    'type',
    'field',
    'fields',
    'choices',
    'choice_provider',
    'pre_value',
    'pre_operator',
    # Anything not listed here will appear last, in alphabetical order
]


class Command(BaseCommand):
    help = ("Takes an existing report config, indents properly, removes default "
            "values, and reorders some column and filter fields.")

    def add_arguments(self, parser):
        parser.add_argument('filepath')

    def handle(self, filepath, *args, **kwargs):
        with open(filepath, encoding='utf-8') as f:
            json_spec = json.load(f)

        json_spec['config']['filters'] = clean_filters(json_spec)
        json_spec['config']['columns'] = clean_columns(json_spec)
        json_spec['config'] = order_dict(json_spec['config'], [
            'title', 'description', 'visible', 'aggregation_columns', 'filters',
            'columns', 'sort_expression', 'configured_charts',
        ])
        json_spec = order_dict(json_spec, [
            'domains', 'server_environment', 'report_id', 'data_source_table', 'config',
        ])

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(six.text_type(json.dumps(json_spec, indent=2)))

        print(textwrap.dedent("""
            Wrote those changes to the existing file.
            Be sure to manually inspect it before committing these changes.
            Consider also adding a detailed description to this config.
        """))


def order_dict(dict_, order):
    positions = {field: position for position, field in enumerate(order)}

    def get_sort_key(item):
        key = item[0]
        return positions.get(key, key)

    return OrderedDict(sorted(list(dict_.items()), key=get_sort_key))


def clean_spec(spec, wrapped):
    new_spec = {}
    for k, v in spec.items():
        if not hasattr(wrapped.__class__, k):
            print("  '{}' is not a valid field for '{}'. Dropping."
                  .format(k, wrapped.__class__.__name__))
        elif getattr(wrapped.__class__, k).default() == v:
            print("  Dropping parameter '{}' because '{}' is the default".format(k, v))
        else:
            new_spec[k] = v
    return new_spec


def clean_filters(json_spec):
    cleaned_filters = []
    for filter_spec in json_spec['config']['filters']:
        print("Checking filter '{}'".format(filter_spec['slug']))
        wrapped_filter = FILTER_SPECS[filter_spec['type']].wrap(filter_spec)
        new_filter_spec = clean_spec(filter_spec, wrapped_filter)
        cleaned_filters.append(order_dict(new_filter_spec, FILTER_PARAMS_ORDER))
    return cleaned_filters


def clean_columns(json_spec):
    static_config = StaticReportConfiguration.wrap(deepcopy(json_spec))
    report_config = ReportConfiguration.wrap(static_config.config)
    cleaned_columns = []
    for col_spec, wrapped_col in zip(json_spec['config']['columns'],
                                     report_config.report_columns):
        print("Checking column '{}'".format(col_spec['column_id']))
        new_col_spec = clean_spec(col_spec, wrapped_col)
        cleaned_columns.append(order_dict(new_col_spec, COLUMN_PARAMS_ORDER))
    return cleaned_columns
