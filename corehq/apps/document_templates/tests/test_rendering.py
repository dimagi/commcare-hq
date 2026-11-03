import pytest

from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    build_combined_template,
    get_preview_context,
    get_variable_names,
    parse_variable_names,
    render_template,
    markdown_to_sanitized_html,
)

VALUES = {'header': '', 'address': '', 'body': '', 'footer': ''}


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


@pytest.mark.parametrize('value, expected', [
    ('', ''),
    ('**bold**', '<p><strong>bold</strong></p>'),
    ('line one\nline two', '<p>line one<br>\nline two</p>'),
    ('Dear {{ first_name }}', '<p>Dear {{ first_name }}</p>'),
    ('{{ x | default("a") }}', '<p>{{ x | default("a") }}</p>'),
    ('<script>alert(1)</script>', 'alert(1)'),
    ('<img src="https://a.test/h.png" onerror="x()">', '<p><img src="https://a.test/h.png"></p>'),
    ('<img src="javascript:x">', '<p><img></p>'),
    ('![h](data:image/png;base64,AAAA)', '<p><img src="data:image/png;base64,AAAA"></p>'),
])
def test_markdown_to_sanitized_html(value, expected):
    assert markdown_to_sanitized_html(value) == expected


def test_combined_template_places_values_in_the_slots():
    combined = build_combined_template({**VALUES, 'body': 'Hello **there**'})
    assert '<div class="letter-body"><p>Hello <strong>there</strong></p></div>' in combined


def test_combined_template_keeps_the_layout():
    combined = build_combined_template(VALUES)
    assert '<tfoot>' in combined
    assert combined.startswith('<!DOCTYPE html>')


def test_combined_template_does_not_run_jinja_in_values():
    combined = build_combined_template({**VALUES, 'body': '{{ 1 + 1 }}'})
    assert '{{ 1 + 1 }}' in combined
    assert '2' not in combined.split('<div class="letter-body">')[1].split('</div>')[0]


def test_preview_context_lists_variables_used_in_values():
    values = {**VALUES, 'address': '{{ name }}\n{{ street }}', 'body': 'Dear {{ name }}'}
    assert get_preview_context(values) == {'name': '', 'street': ''}


def test_preview_context_is_empty_without_variables():
    assert get_preview_context(VALUES) == {}


def test_preview_context_reports_a_syntax_error():
    with pytest.raises(DocumentRenderError, match='syntax error'):
        get_preview_context({**VALUES, 'body': '{% if %}'})


def test_render_template_fills_in_the_context():
    html = render_template({**VALUES, 'body': 'Dear {{ name }}'}, {'name': 'Ada'})
    assert '<p>Dear Ada</p>' in html


def test_render_template_escapes_context_values():
    html = render_template({**VALUES, 'body': '{{ name }}'}, {'name': '<script>x</script>'})
    assert '<script>x</script>' not in html
    assert '&lt;script&gt;' in html


def test_render_template_requires_every_variable():
    with pytest.raises(DocumentRenderError, match="'name' is undefined"):
        render_template({**VALUES, 'body': '{{ name }}'}, {})


def test_render_template_is_sandboxed():
    with pytest.raises(DocumentRenderError, match='Range too big'):
        render_template({**VALUES, 'body': '{{ range(1000000) | list | length }}'}, {})


def test_markdown_emphasis_mangles_dunder_names_in_values():
    # Python-Markdown turns __word__ into <strong>, so such names cannot be used in a value
    html = markdown_to_sanitized_html("{{ ''.__class__.__mro__ }}")
    assert html == "<p>{{ ''.<strong>class</strong>.<strong>mro</strong> }}</p>"
