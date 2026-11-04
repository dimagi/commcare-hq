from io import BytesIO

import pytest
from PIL import Image
from reportlab.platypus import ListFlowable, Paragraph

from corehq.apps.document_templates.models import Area
from corehq.apps.document_templates.rendering import (
    DocumentRenderError,
    MAX_AREA_LENGTH,
    MAX_LOOP_ITEMS,
    _image_flowable,
    get_area_definitions,
    _markdown_to_flowables,
    _markdown_to_sanitized_html,
    _parse_variable_names,
    get_area_names,
    generate_document,
    get_variable_names,
    render_pdf,
)

VALUES = {'header': '', 'address': '', 'body': '', 'footer': ''}


def _areas(values):
    return {name: Area(value=value) for name, value in values.items()}


def _generate(values, context):
    document = generate_document(_areas(values), context)
    return {name: area.value for name, area in document.items()}


def test_get_area_names():
    assert get_area_names() == ['header', 'address', 'body', 'footer']


def test_area_definitions_describe_the_size_and_position_of_each_area():
    assert {area.name: (area.label, area.description) for area in get_area_definitions()} == {
        'header': ('Header', '7 x 1 in, at the top of the first page. An image is centered.'),
        'address': ('Address', '7 x 1.25 in, below the header on the first page. An image is left-aligned.'),
        'body': ('Body', '7 in wide, below the address and over the pages that follow. An image is left-aligned.'),
        'footer': ('Footer', '7 x 1 in, at the bottom of every page. An image is centered.'),
    }


@pytest.mark.parametrize('text, expected', [
    ('', []),
    ('no variables here', []),
    ('{{ b }} {{ a }}', ['b', 'a']),
    ('{{ a }} {{ b }} {{ a }}', ['a', 'b']),
    ('{{ a | safe }} {{ b | default("x") }}', ['a', 'b']),
    ('{% for item in items %}{{ item }} {{ other }}{% endfor %}', ['items', 'other']),
    ('{% set x = 1 %}{{ x }} {{ y }}', ['y']),
    ('{% if a %}{{ b }}{% endif %}', ['a', 'b']),
])
def test_parse_variable_names(text, expected):
    assert _parse_variable_names(text) == expected


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
    assert _markdown_to_sanitized_html(value) == expected


def test_variable_names_lists_variables_used_in_areas():
    area_values = {**VALUES, 'address': '{{ name }}\n{{ street }}', 'body': 'Dear {{ name }}'}
    assert get_variable_names(_areas(area_values)) == ['name', 'street']


def test_variable_names_is_empty_without_variables():
    assert get_variable_names(_areas(VALUES)) == []


def test_variable_names_reports_a_syntax_error():
    with pytest.raises(DocumentRenderError, match='syntax error in body, line 1'):
        get_variable_names(_areas({**VALUES, 'body': '{% if %}'}))


def test_generate_document_fills_in_the_context():
    area_values = {**VALUES, 'address': '{{ name }}', 'body': 'Dear {{ name }}'}
    rendered = _generate(area_values, {'name': 'Ada'})
    assert rendered == {**VALUES, 'address': 'Ada', 'body': 'Dear Ada'}


@pytest.mark.parametrize('value, expected', [
    ('**x**', r'\*\*x\*\*'),
    ('<script>x</script>', '&lt;script&gt;x&lt;/script&gt;'),
    ('[a](http://b.test)', r'\[a\]\(http://b\.test\)'),
    ('# not a heading', r'\# not a heading'),
])
def test_generate_document_makes_context_values_literal(value, expected):
    rendered = _generate({**VALUES, 'body': '{{ name }}'}, {'name': value})
    assert rendered['body'] == expected


def test_generate_document_keeps_authors_markdown():
    rendered = _generate({**VALUES, 'body': '**Dear** {{ name }}'}, {'name': 'Ada'})
    assert rendered['body'] == '**Dear** Ada'


def test_generate_document_requires_every_variable():
    with pytest.raises(DocumentRenderError, match="body: 'name' is undefined"):
        _generate({**VALUES, 'body': '{{ name }}'}, {})


def test_generate_document_is_sandboxed():
    with pytest.raises(DocumentRenderError, match='Range too big'):
        _generate({**VALUES, 'body': '{{ range(1000000) | list | length }}'}, {})


@pytest.mark.parametrize('text, message', [
    ("{{ 'x' * 10**9 }}", 'Repeated value too big'),
    ("{{ 10**9 * 'x' }}", 'Repeated value too big'),
    ("{{ [0] * 10**9 }}", 'Repeated value too big'),
    ("{{ 2**10000 }}", 'Power too big'),
    ("{{ 9**999**999 }}", 'Power too big'),
    ("{{ '%1000000000d' % 1 }}", 'String formatting is not allowed'),
    ("{% for a in range(1000) %}{% for b in range(1000) %}{% endfor %}{% endfor %}", 'Too many loop iterations'),
    ("{% for a in range(MAX) %}{% endfor %}".replace('MAX', str(MAX_LOOP_ITEMS + 1)), 'Too many loop iterations'),
    ("{{ 'x' * 50000 }}{{ 'x' * 50001 }}", 'too long once rendered'),
])
def test_generate_document_limits_resource_use(text, message):
    with pytest.raises(DocumentRenderError, match=message):
        _generate({**VALUES, 'body': text}, {})


@pytest.mark.parametrize('text, expected', [
    ('{% for i in range(3) %}{{ i }}{% endfor %}', '012'),
    ("{{ 'ab' * 3 }}", 'ababab'),
    ('{{ 2 ** 10 }}', '1024'),
    ('{{ 7 % 4 }}', '3'),
])
def test_generate_document_allows_ordinary_use(text, expected):
    assert _generate({**VALUES, 'body': text}, {})['body'] == expected


def test_generate_document_range_budget_is_per_area():
    text = '{% for i in range(6000) %}{% endfor %}'
    assert _generate({**VALUES, 'body': text, 'footer': text}, {})


def test_generate_document_rejects_a_long_area():
    with pytest.raises(DocumentRenderError, match='body is too long'):
        _generate({**VALUES, 'body': 'x' * (MAX_AREA_LENGTH + 1)}, {})


def test_variable_names_rejects_a_long_area():
    with pytest.raises(DocumentRenderError, match='body is too long'):
        get_variable_names(_areas({**VALUES, 'body': 'x' * (MAX_AREA_LENGTH + 1)}))


def test_generate_document_reports_a_syntax_error():
    with pytest.raises(DocumentRenderError, match='syntax error in footer, line 1'):
        _generate({**VALUES, 'footer': '{% if %}'}, {})


def test_markdown_emphasis_mangles_dunder_names_in_values():
    # Python-Markdown turns __word__ into <strong>, so such names cannot be used in a value
    html = _markdown_to_sanitized_html("{{ ''.__class__.__mro__ }}")
    assert html == "<p>{{ ''.<strong>class</strong>.<strong>mro</strong> }}</p>"


def _markups(flowables):
    return [flowable.text for flowable in flowables]


@pytest.mark.parametrize('markdown_text, expected', [
    ('plain', ['plain']),
    ('**b** *i*', ['<b>b</b> <i>i</i>']),
    ('line one\nline two', ['line one<br/>line two']),
    ('a < b & c', ['a &lt; b &amp; c']),
    ('`code`', ['<font name="Courier">code</font>']),
    ('[link](https://a.test)', ['<a href="https://a.test" color="#0b57d0">link</a>']),
    ('one\n\ntwo', ['one', 'two']),
    ('# Title', ['Title']),
    ('> quoted', ['quoted']),
    ('<style>p { color: red }</style>text', ['text']),
    ('a [[blank:3]] b', ['a <u>&nbsp;&nbsp;&nbsp;</u> b']),
    ('[[blank]]', [f'<u>{"&nbsp;" * 20}</u>']),
    ('[[blank:999]]', [f'<u>{"&nbsp;" * 100}</u>']),
    ('[[blank:x]] [[blanks]]', ['[[blank:x]] [[blanks]]']),
    ('', []),
])
def test_markdown_to_flowables_paragraphs(markdown_text, expected):
    flowables = _markdown_to_flowables(markdown_text)
    assert all(isinstance(flowable, Paragraph) for flowable in flowables)
    assert _markups(flowables) == expected


@pytest.mark.parametrize('markdown_text, style_name', [
    ('# One', 'Heading1'),
    ('## Two', 'Heading2'),
    ('###### Six', 'Heading3'),
    ('> quoted', 'quote'),
])
def test_markdown_to_flowables_styles(markdown_text, style_name):
    assert _markdown_to_flowables(markdown_text)[0].style.name == style_name


@pytest.mark.parametrize('markdown_text, bullet_type, items', [
    ('- a\n- **b**', 'bullet', ['a', '<b>b</b>']),
    ('1. a\n2. b', '1', ['a', 'b']),
])
def test_markdown_to_flowables_lists(markdown_text, bullet_type, items):
    [flowable] = _markdown_to_flowables(markdown_text)
    assert isinstance(flowable, ListFlowable)
    assert flowable._flowables[0].__class__.__name__ == 'ListItem'
    assert flowable._bulletType == bullet_type
    assert [item._flowables[0].text for item in flowable._flowables] == items


def _document(**areas):
    return {name: Area(value=areas.get(name, '')) for name in VALUES}


def test_render_pdf_returns_a_pdf():
    assert render_pdf([_document(body='Hello')]).startswith(b'%PDF')


def test_render_pdf_rejects_an_unknown_area_type():
    document = {**_document(), 'body': Area(type='unknown', value='x')}
    with pytest.raises(ValueError, match="Unknown area type: 'unknown'"):
        render_pdf([document])


def test_render_pdf_starts_each_document_on_a_new_page():
    one = render_pdf([_document(body='Hello')])
    two = render_pdf([_document(body='Hello'), _document(body='World')])
    assert two.count(b'/Type /Page\n') == one.count(b'/Type /Page\n') + 1


def test_blank_is_underlined():
    [paragraph] = _markdown_to_flowables('a [[blank:5]] b')
    paragraph.wrap(400, 100)
    frags = paragraph.blPara.lines[0].words
    assert [frag.text for frag in frags if frag.us_lines] == ['\xa0'] * 5


def test_render_pdf_clips_overflowing_areas():
    long_text = '\n\n'.join(['paragraph'] * 200)
    render_pdf([_document(header=long_text, address=long_text, footer=long_text)])


def test_render_pdf_flows_the_body_over_pages():
    short = render_pdf([_document(body='paragraph')])
    long = render_pdf([_document(body='\n\n'.join(['paragraph'] * 200))])
    assert long.count(b'/Type /Page\n') > short.count(b'/Type /Page\n')


def test_generate_document_keeps_other_area_types():
    image = Area(type='image', value=_png())
    document = generate_document({**_areas(VALUES), 'body': image}, {})
    assert document['body'] is image


def test_variable_names_ignores_other_area_types():
    areas = {**_areas(VALUES), 'body': Area(type='image', value='{{ name }}')}
    assert get_variable_names(areas) == []


def _png(size=(100, 50)):
    buffer = BytesIO()
    Image.new('RGBA', size, color=(200, 30, 30, 128)).save(buffer, format='PNG')
    return buffer.getvalue()


def _image(data):
    return Area(type='image', value=data)


@pytest.mark.parametrize('image_size, frame, expected', [
    ((100, 50), (504, 72), (100, 50)),  # never scaled up
    ((2000, 100), (504, 72), (504, 25.2)),  # too wide
    ((100, 1000), (504, 72), (7.2, 72)),  # too tall
    ((4000, 4000), (504, 612), (504, 504)),
])
def test_image_is_scaled_down_to_fit_keeping_its_ratio(image_size, frame, expected):
    flowable = _image_flowable(_png(image_size), *frame, 'LEFT')
    assert (round(flowable.drawWidth, 1), round(flowable.drawHeight, 1)) == expected


@pytest.mark.parametrize('alignment', ['LEFT', 'CENTER'])
def test_image_is_aligned(alignment):
    assert _image_flowable(_png(), 504, 72, alignment).hAlign == alignment


@pytest.mark.parametrize('area_name', list(VALUES))
def test_render_pdf_draws_an_image_in_any_area(area_name):
    pdf = render_pdf([{**_document(), area_name: _image(_png())}])
    assert b'/Subtype /Image' in pdf


def test_render_pdf_draws_an_empty_image_area_as_blank():
    assert b'/Subtype /Image' not in render_pdf([{**_document(), 'header': _image(b'')}])


@pytest.mark.parametrize('area_name', list(VALUES))
def test_render_pdf_fits_an_image_that_is_larger_than_the_area(area_name):
    render_pdf([{**_document(), area_name: _image(_png((4000, 4000)))}])


def test_render_pdf_moves_a_body_image_that_does_not_fit_below_the_address_to_the_next_page():
    small = render_pdf([{**_document(), 'body': _image(_png((100, 50)))}])
    tall = render_pdf([{**_document(), 'body': _image(_png((100, 4000)))}])
    assert small.count(b'/Type /Page\n') == 1
    assert tall.count(b'/Type /Page\n') == 2


def test_generate_document_renders_markdown_around_an_image():
    areas = {**_areas(VALUES), 'header': _image(_png()), 'body': Area(value='Dear {{ name }}')}
    document = generate_document(areas, {'name': 'Ada'})
    assert document['header'] is areas['header']
    assert document['body'].value == 'Dear Ada'
    assert b'/Subtype /Image' in render_pdf([document])


def test_generate_document_reports_an_image_that_cannot_be_read():
    with pytest.raises(DocumentRenderError, match='header: the image cannot be read'):
        generate_document({**_areas(VALUES), 'header': _image(b'not an image')}, {})
