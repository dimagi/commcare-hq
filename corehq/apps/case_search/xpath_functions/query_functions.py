from datetime import datetime

from django.utils.translation import gettext as _

from eulxml.xpath import serialize
from eulxml.xpath.ast import Step
from jsonobject.exceptions import BadValueError

from couchforms.geopoint import GeoPoint

from corehq.apps.case_search.dsl_utils import unwrap_value
from corehq.apps.case_search.exceptions import XPathFunctionException
from corehq.apps.es import filters
from corehq.apps.es.queries import DISTANCE_UNITS
from corehq.apps.es.case_search import (
    case_property_geo_distance,
    case_property_query,
    sounds_like_text_query,
    case_property_starts_with,
)

from .utils import confirm_args_count


def not_(node, context):
    from corehq.apps.case_search.filter_dsl import build_filter_from_ast
    confirm_args_count(node, 1)
    return filters.NOT(build_filter_from_ast(node.args[0], context))


def starts_with(node, context):
    property_name, search_value = node.args
    property_name = _property_name_to_string(property_name, node)
    return case_property_starts_with(property_name, search_value)


def selected_any(node, context):
    return _selected_query(node, context, operator='or')


def selected_all(node, context):
    return _selected_query(node, context, operator='and')


def _selected_query(node, context, operator):
    confirm_args_count(node, 2)

    property_name, search_values = node.args
    property_name = _property_name_to_string(property_name, node)
    return case_property_query(property_name, search_values, fuzzy=context.fuzzy, multivalue_mode=operator)


def within_distance(node, context):
    confirm_args_count(node, 4)
    property_name, coords, distance, unit = node.args
    property_name = _property_name_to_string(property_name, node)

    try:
        geo_point = GeoPoint.from_string(coords, flexible=True)
    except BadValueError as e:
        raise XPathFunctionException(
            _(f"The second argument to '{node.name}' must be valid coordinates"),
            serialize(node)
        ) from e

    try:
        distance = float(distance)
    except ValueError as e:
        raise XPathFunctionException(
            _(f"The third argument to '{node.name}' must be a number, got '{distance}'"),
            serialize(node)
        ) from e

    if unit not in DISTANCE_UNITS:
        raise XPathFunctionException(
            _(f"'{unit}' is not a valid distance unit. Expected one of {', '.join(DISTANCE_UNITS)}"),
            serialize(node)
        )

    return case_property_geo_distance(property_name, geo_point, **{unit: distance})


def phonetic_match(node, context):
    confirm_args_count(node, 2)
    property_name, value = node.args
    property_name = _property_name_to_string(property_name, node)

    return sounds_like_text_query(property_name, value)


def fuzzy_match(node, context):
    """fuzzy-match(alias, 'pinky')"""
    confirm_args_count(node, 2)
    property_name = _property_name_to_string(node.args[0], node)
    value = unwrap_value(node.args[1], context)

    return case_property_query(property_name, value, fuzzy=True)


def fuzzy_date(node, context):
    """fuzzy-match(dob, '2024-12-03')"""
    confirm_args_count(node, 2)
    property_name = _property_name_to_string(node.args[0], node)
    value = unwrap_value(node.args[1], context)

    if not validate_date(value):
        raise XPathFunctionException(
            _(f"'{value}' is not a valid date. Expected 'YYYY-MM-DD"),
            serialize(node)
        )

    return case_property_query(property_name, date_permutations(value), boost_first=True)


def date_permutations(date_str):
    [year, month, day] = date_str.split('-')
    reverse_decade = year[:2] + year[3] + year[2]
    reverse_month = month[::-1]
    reverse_day = day[::-1]
    permutations = [
        date_str,
        f"{year}-{day}-{month}",
        f"{year}-{reverse_month}-{day}",
        f"{year}-{day}-{reverse_month}",
        f"{year}-{month}-{reverse_day}",
        f"{year}-{reverse_day}-{month}",
        f"{year}-{reverse_month}-{reverse_day}",
        f"{year}-{reverse_day}-{reverse_month}",
        f"{reverse_decade}-{month}-{day}",
        f"{reverse_decade}-{day}-{month}",
        f"{reverse_decade}-{reverse_month}-{day}",
        f"{reverse_decade}-{day}-{reverse_month}",
        f"{reverse_decade}-{month}-{reverse_day}",
        f"{reverse_decade}-{reverse_day}-{month}",
        f"{reverse_decade}-{reverse_month}-{reverse_day}",
        f"{reverse_decade}-{reverse_day}-{reverse_month}"
    ]
    valid_permutations = [p for p in permutations if validate_date(p)]
    return valid_permutations


def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%Y-%m-%d')  # change the date format if needed
        return True
    except ValueError:
        return False


def _property_name_to_string(value, node):
    if isinstance(value, Step):
        return serialize(value)
    if isinstance(value, str):
        return value
    raise XPathFunctionException(
        _(f"The first argument to '{node.name}' must be a valid case property name"),
        serialize(node)
    )


def match_all(node, context):
    if len(node.args):
        raise XPathFunctionException(
            _("'match-all()' does not take any arguments"),
            serialize(node)
        )
    return filters.match_all()


def match_none(node, context):
    if len(node.args):
        raise XPathFunctionException(
            _("'match-none()' does not take any arguments"),
            serialize(node)
        )
    return filters.match_none()
