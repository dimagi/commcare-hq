import pytest
from reportlab.platypus import Paragraph

from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    _parse_variable_names,
    _render_areas,
    _text_to_flowables,
    get_area_names,
    get_preview_context,
    render_pdf,
    render_preview,
)

VALUES = {'header': '', 'address': '', 'body': '', 'footer': ''}


def test_get_area_names():
    assert get_area_names() == ['header', 'address', 'body', 'footer']


@pytest.mark.parametrize('area_value, expected', [
    ('', []),
    ('no variables here', []),
    ('{{ b }} {{ a }}', ['b', 'a']),
    ('{{ a }} {{ b }} {{ a }}', ['a', 'b']),
    ('{{ a | safe }} {{ b | default("x") }}', ['a', 'b']),
    ('{% for item in items %}{{ item }} {{ other }}{% endfor %}', ['items', 'other']),
    ('{% set x = 1 %}{{ x }} {{ y }}', ['y']),
    ('{% if a %}{{ b }}{% endif %}', ['a', 'b']),
])
def test_parse_variable_names(area_value, expected):
    assert _parse_variable_names(area_value) == expected


def test_preview_context_lists_variables_used_in_areas():
    area_values = {**VALUES, 'address': '{{ name }}\n{{ street }}', 'body': 'Dear {{ name }}'}
    assert get_preview_context(area_values) == {'name': '', 'street': ''}


def test_preview_context_is_empty_without_variables():
    assert get_preview_context(VALUES) == {}


def test_preview_context_reports_a_syntax_error():
    with pytest.raises(DocumentRenderError, match='syntax error in body, line 1'):
        get_preview_context({**VALUES, 'body': '{% if %}'})


def test_render_areas_fills_in_the_context():
    area_values = {**VALUES, 'address': '{{ name }}', 'body': 'Dear {{ name }}'}
    rendered = _render_areas(area_values, {'name': 'Ada'})
    assert rendered == {**VALUES, 'address': 'Ada', 'body': 'Dear Ada'}


def test_render_areas_requires_every_variable():
    with pytest.raises(DocumentRenderError, match="body: 'name' is undefined"):
        _render_areas({**VALUES, 'body': '{{ name }}'}, {})


def test_render_areas_is_sandboxed():
    with pytest.raises(DocumentRenderError, match='Range too big'):
        _render_areas({**VALUES, 'body': '{{ range(1000000) | list | length }}'}, {})


def test_render_areas_reports_a_syntax_error():
    with pytest.raises(DocumentRenderError, match='syntax error in footer, line 1'):
        _render_areas({**VALUES, 'footer': '{% if %}'}, {})


def _markups(flowables):
    return [flowable.text for flowable in flowables]


@pytest.mark.parametrize('text, expected', [
    ('plain', ['plain']),
    ('line one\nline two', ['line one<br/>line two']),
    ('line one\r\nline two', ['line one<br/>line two']),
    ('one\n\ntwo', ['one', 'two']),
    ('one\r\n\r\ntwo', ['one', 'two']),
    ('one\n  \n\n two ', ['one', 'two']),
    ('a < b & c', ['a &lt; b &amp; c']),
    ('**not bold** # not a heading', ['**not bold** # not a heading']),
    ('', []),
    ('\n\n', []),
])
def test_text_to_flowables(text, expected):
    flowables = _text_to_flowables(text)
    assert all(isinstance(flowable, Paragraph) for flowable in flowables)
    assert _markups(flowables) == expected


def _document(**areas):
    return {area: {'type': 'text', 'value': areas.get(area, '')} for area in VALUES}


def test_render_pdf_returns_a_pdf():
    assert render_pdf([_document(body='Hello')]).startswith(b'%PDF')


def test_render_pdf_rejects_an_unknown_area_type():
    document = {**_document(), 'body': {'type': 'image', 'value': 'x.png'}}
    with pytest.raises(ValueError, match="Unknown area type: 'image'"):
        render_pdf([document])


def test_render_pdf_starts_each_document_on_a_new_page():
    one = render_pdf([_document(body='Hello')])
    two = render_pdf([_document(body='Hello'), _document(body='World')])
    assert two.count(b'/Type /Page\n') == one.count(b'/Type /Page\n') + 1


def test_render_pdf_clips_overflowing_areas():
    long_text = '\n\n'.join(['paragraph'] * 200)
    render_pdf([_document(header=long_text, address=long_text, footer=long_text)])


def test_render_pdf_flows_the_body_over_pages():
    short = render_pdf([_document(body='paragraph')])
    long = render_pdf([_document(body='\n\n'.join(['paragraph'] * 200))])
    assert long.count(b'/Type /Page\n') > short.count(b'/Type /Page\n')


def test_render_preview_returns_a_pdf():
    pdf = render_preview({**VALUES, 'body': 'Dear {{ name }}'}, {'name': 'Ada'})
    assert pdf.startswith(b'%PDF')
