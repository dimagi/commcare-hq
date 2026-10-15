import pytest

from corehq.apps.document_templates.rendering import (
    get_variable_names,
    parse_variable_names,
)


def test_get_variable_names_reads_the_us_letter_template():
    assert get_variable_names() == ['header', 'address', 'body', 'footer']


@pytest.mark.parametrize('source, expected', [
    ('', []),
    ('no variables here', []),
    ('{{ b }} {{ a }}', ['b', 'a']),
    ('{{ a }} {{ b }} {{ a }}', ['a', 'b']),
    ('{{ a | safe }} {{ b | default("x") }}', ['a', 'b']),
    ('{% for item in items %}{{ item }} {{ other }}{% endfor %}', ['items', 'other']),
    ('{% set x = 1 %}{{ x }} {{ y }}', ['y']),
    ('{% if a %}{{ b }}{% endif %}', ['a', 'b']),
])
def test_parse_variable_names(source, expected):
    assert parse_variable_names(source) == expected
