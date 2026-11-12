"""
Tests for rendering and validating ``OpenmrsImporter.report_params``.

Report params are user-supplied, so they must never be evaluated by a
template engine. Only the documented ``{{ today }}`` and
``{{ location }}`` placeholders are substituted; everything else is a
literal string.
"""
import doctest
from datetime import datetime
from unittest.mock import patch

import pytest
from unmagic import fixture, use

from corehq.motech.exceptions import ConfigurationError
from corehq.motech.openmrs.models import (
    REPORT_PARAM_PLACEHOLDERS,
    parse_params,
    validate_report_params,
)

TODAY = datetime(2026, 10, 23)


class FakeLocation:
    name = 'Cape Town'
    metadata = {'openmrs_uuid': 'loc-uuid'}


class LocationWithoutUuid:
    name = 'Cape Town'
    metadata = {}


@fixture
def fixed_today():
    with patch('corehq.motech.openmrs.models.datetime') as dt:
        dt.today.return_value = TODAY
        yield


@use(fixed_today)
@pytest.mark.parametrize('value, expected', [
    ('{{ today }}', '2026-10-23'),
    ('{{today}}', '2026-10-23'),
    ('{{   today   }}', '2026-10-23'),
    ('{{ location }}', 'loc-uuid'),
    ('from {{ today }} at {{ location }}', 'from 2026-10-23 at loc-uuid'),
    ('plain text', 'plain text'),
    # Unknown placeholders are left as literals
    ('{{ tomorrow }}', '{{ tomorrow }}'),
    # Jinja2 syntax is not evaluated
    ("{{ ''.__class__ }}", "{{ ''.__class__ }}"),
    ('{{ today | upper }}', '{{ today | upper }}'),
    ('{% if today %}x{% endif %}', '{% if today %}x{% endif %}'),
    # str.format syntax is not evaluated either
    ('{today.__class__}', '{today.__class__}'),
])
def test_parse_params_strings(value, expected):
    assert parse_params({'p': value}, FakeLocation()) == {'p': expected}


def test_parse_params_without_location():
    # Preserves the previous Jinja2 behaviour of rendering None as "None"
    assert parse_params({'p': '{{ location }}'}) == {'p': 'None'}


@use(fixed_today)
@pytest.mark.parametrize('placeholder', REPORT_PARAM_PLACEHOLDERS)
def test_parse_params_substitutes_every_placeholder(placeholder):
    parsed = parse_params({'p': f'{{{{ {placeholder} }}}}'}, FakeLocation())
    assert '{{' not in parsed['p']


def test_parse_params_location_without_uuid():
    with pytest.raises(ConfigurationError, match='"Cape Town" has no "openmrs_uuid"'):
        parse_params({'p': '{{ location }}'}, LocationWithoutUuid())


@use(fixed_today)
def test_parse_params_ignores_location_if_unused():
    params = {'p': '{{ today }}'}
    assert parse_params(params, LocationWithoutUuid()) == {'p': '2026-10-23'}


def test_parse_params_leaves_non_strings_unchanged():
    params = {'n': 1, 'b': True, 'none': None, 'list': ['{{ today }}']}
    assert parse_params(params) == params


@pytest.mark.parametrize('params', [
    {},
    {'endDate': '{{ today }}'},
    {'endDate': '{{today}}', 'location': '{{ location }}'},
    {'text': 'no placeholders'},
    {'n': 1, 'b': True, 'none': None},
    {'braces': '{not a template}'},
])
def test_validate_report_params_accepts(params):
    validate_report_params(params)


@pytest.mark.parametrize('value', [
    '{{ tomorrow }}',
    "{{ ''.__class__ }}",
    '{{ today | upper }}',
    '{{ today }} and {{ bad }}',
    '{% if today %}x{% endif %}',
    '{# comment #}',
    '{{ unterminated',
])
def test_validate_report_params_rejects(value):
    with pytest.raises(ValueError, match='endDate'):
        validate_report_params({'endDate': value})


def test_doctests():
    import corehq.motech.openmrs.models

    results = doctest.testmod(corehq.motech.openmrs.models)
    assert results.failed == 0
