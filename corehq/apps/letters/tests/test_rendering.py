from types import SimpleNamespace

import pytest
from jinja2 import TemplateSyntaxError

from corehq.apps.letters.rendering import (
    UNGROUPED,
    LetterRenderError,
    build_sections,
    render_letter,
    validate_template,
)


def _case(case_id, name='n', **props):
    return SimpleNamespace(case_id=case_id, name=name, external_id=None, owner_id='o1', case_json=props)


def test_render_substitutes_properties():
    assert render_letter('<p>Dear {{ first }}</p>', {'first': 'Ana'}) == '<p>Dear Ana</p>'


def test_render_escapes_property_values():
    out = render_letter('<p>{{ v }}</p>', {'v': '<script>x()</script>'})
    assert '<script>' not in out
    assert '&lt;script&gt;' in out


@pytest.mark.parametrize('body, forbidden', [
    ('<script>alert(1)</script><p>hi</p>', '<script'),
    ('<img src="x" onerror="alert(1)">', 'onerror'),
    ('<a href="javascript:alert(1)">x</a>', 'javascript:'),
    ('<a href="data:text/html,hi">x</a>', 'data:text/html'),
])
def test_render_strips_active_content(body, forbidden):
    assert forbidden not in render_letter(body, {})


def test_render_keeps_style_block_and_data_image():
    body = '<style>p {color: red}</style><img src="data:image/png;base64,AAAA">'
    out = render_letter(body, {})
    assert '<style>' in out
    assert 'data:image/png;base64,AAAA' in out


def test_render_missing_property_raises():
    with pytest.raises(LetterRenderError):
        render_letter('{{ missing }}', {})


@pytest.mark.parametrize('body', [
    '{{ 1 / 0 }}',
    "{{ ''.__class__.__mro__ }}",  # sandbox SecurityError
])
def test_render_runtime_errors_raise(body):
    with pytest.raises(LetterRenderError):
        render_letter(body, {})


def test_validate_template_rejects_bad_syntax():
    with pytest.raises(TemplateSyntaxError):
        validate_template('{% if %}')


def test_validate_template_accepts_comparison():
    validate_template('{% if a > b %}{{ a }}{% endif %}')


def test_build_sections_no_grouping_single_section_sorted_by_name():
    templates = {'1': '{{ case_name }}'}
    cases = [_case('b', 'Bob', tpl='1'), _case('a', 'Ana', tpl='1')]
    sections, skipped = build_sections(cases, templates, 'tpl')
    assert skipped == []
    assert [s.title for s in sections] == [None]
    assert sections[0].letters == ['Ana', 'Bob']


def test_build_sections_sort_by_property():
    templates = {'1': '{{ case_name }}'}
    cases = [_case('a', 'Ana', tpl='1', rank='2'), _case('b', 'Bob', tpl='1', rank='1')]
    sections, _ = build_sections(cases, templates, 'tpl', sort_by='rank')
    assert sections[0].letters == ['Bob', 'Ana']


def test_build_sections_grouped_blank_and_missing_go_to_ungrouped_last():
    templates = {'1': '{{ case_name }}'}
    cases = [
        _case('a', 'Ana', tpl='1', district='North'),
        _case('b', 'Bob', tpl='1', district=''),
        _case('c', 'Cy', tpl='1'),
        _case('d', 'Di', tpl='1', district='East'),
    ]
    sections, _ = build_sections(cases, templates, 'tpl', group_by='district')
    assert [str(s.title) for s in sections] == ['East', 'North', str(UNGROUPED)]
    assert sections[-1].letters == ['Bob', 'Cy']


@pytest.mark.parametrize('tpl_value', [None, '', 'abc', '999'])
def test_build_sections_bad_template_ref_skipped(tpl_value):
    props = {} if tpl_value is None else {'tpl': tpl_value}
    cases = [_case('a', 'Ana', **props), _case('b', 'Bob', tpl='1')]
    sections, skipped = build_sections(cases, {'1': 'ok'}, 'tpl')
    assert [s.case_id for s in skipped] == ['a']
    assert sections[0].letters == ['ok']


def test_build_sections_render_error_skipped_others_render():
    cases = [_case('a', 'Ana', tpl='1'), _case('b', 'Bob', tpl='1', x='hi')]
    sections, skipped = build_sections(cases, {'1': '{{ x }}'}, 'tpl')
    assert [(s.case_id, s.case_name) for s in skipped] == [('a', 'Ana')]
    assert sections[0].letters == ['hi']


def test_build_sections_all_skipped_returns_no_sections():
    sections, skipped = build_sections([_case('a', tpl='9')], {}, 'tpl')
    assert sections == []
    assert len(skipped) == 1


@pytest.mark.parametrize('href', [
    '&#x64;ata:text/html,hi',
    '&#100;ata:text/html,hi',
    'DATA:text/html,hi',
    '  data:text/html,hi',
])
def test_render_strips_obfuscated_data_href(href):
    out = render_letter(f'<a href="{href}">x</a>', {})
    assert 'href' not in out


def test_build_sections_sort_by_name_column():
    cases = [_case('a', 'Zed', tpl='1'), _case('b', 'Amy', tpl='1')]
    sections, _ = build_sections(cases, {'1': '{{ name }}'}, 'tpl', sort_by='owner_id')
    assert sections[0].letters == ['Amy', 'Zed']  # equal keys tie-break on case name
    sections, _ = build_sections(cases, {'1': '{{ name }}'}, 'tpl', sort_by='name')
    assert sections[0].letters == ['Amy', 'Zed']


def test_build_sections_group_by_name_column():
    cases = [_case('a', 'Zed', tpl='1'), _case('b', 'Amy', tpl='1')]
    sections, _ = build_sections(cases, {'1': 'x'}, 'tpl', group_by='name')
    assert [s.title for s in sections] == ['Amy', 'Zed']


def test_build_sections_template_id_from_column():
    case = _case('a', 'Ana')
    case.owner_id = '1'
    sections, skipped = build_sections([case], {'1': '{{ name }}-{{ owner_id }}'}, 'owner_id')
    assert skipped == []
    assert sections[0].letters == ['Ana-1']


def test_build_sections_sort_ties_break_by_name():
    cases = [_case('a', 'Zed', tpl='1', rank='1'), _case('b', 'Amy', tpl='1', rank='1')]
    sections, _ = build_sections(cases, {'1': '{{ case_name }}'}, 'tpl', sort_by='rank')
    assert sections[0].letters == ['Amy', 'Zed']
