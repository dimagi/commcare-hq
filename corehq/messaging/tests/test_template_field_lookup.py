import pytest

from corehq.form_processor.models import CommCareCase
from corehq.messaging.templating import (
    CaseMessagingTemplateParam,
    MessagingTemplateFormatter,
    MessagingTemplateRenderer,
    NestedDictTemplateParam,
    SimpleDictTemplateParam,
)


def _renderer():
    case = CommCareCase(
        domain='test-domain',
        case_id='abc123',
        name='Alice',
        type='person',
        case_json={'prop': 'value'},
    )
    renderer = MessagingTemplateRenderer()
    renderer.set_context_param('case', CaseMessagingTemplateParam(case))
    renderer.set_context_param(
        'recipient', SimpleDictTemplateParam({'name': 'Bob'})
    )
    renderer.set_context_param(
        'user', NestedDictTemplateParam({'user_data': {'clinic': 'North'}})
    )
    return renderer


@pytest.mark.parametrize(
    'template, expected',
    [
        ('{case.name}', 'Alice'),
        ('{case.prop}', 'value'),
        ('{case._id}', 'abc123'),
        ('{recipient.name}', 'Bob'),
        ('{user.user_data.clinic}', 'North'),
        ('{case}', '(?)'),
        ('{case.unknown}', '(?)'),
        ('{case.unknown.unknown}', '(?)'),
        ('{unknown}', '(?)'),
        ('{recipient.name} and {case.name}', 'Bob and Alice'),
    ],
)
def test_documented_fields_render(template, expected):
    assert _renderer().render(template) == expected


@pytest.mark.parametrize(
    'template',
    [
        '{recipient.__class__}',
        '{unknown.__class__.__init__.__globals__}',
        '{unknown.__class__.__init__.__globals__[__name__]}',
        '{unknown.__class__.__init__.__globals__[Group].save.__globals__[settings].SECRET_KEY}',
        '{recipient._SimpleDictTemplateParam__dict_of_values}',
        '{user._NestedDictTemplateParam__dict_of_values}',
        '{case._CaseMessagingTemplateParam__case}',
        '{case._CaseMessagingTemplateParam__case.domain}',
        '{recipient[name]}',
        '{recipient.name[0]}',
    ],
)
def test_fields_outside_template_data_render_unknown(template):
    assert _renderer().render(template) == '(?)'


@pytest.mark.parametrize(
    'template',
    [
        '{recipient.name!r}',
        '{recipient.name!s}',
        '{recipient.name!a}',
    ],
)
def test_conversions_are_ignored(template):
    assert _renderer().render(template) == 'Bob'


class _SpecRecorder:
    """Renders its format spec, to show what a nested spec field resolved to"""

    def __format__(self, spec):
        return spec


def test_nested_format_spec_field_is_looked_up_safely():
    params = {'x': _SpecRecorder(), 'y': SimpleDictTemplateParam({})}
    rendered = MessagingTemplateFormatter().vformat(
        '{x:{y.__class__}}', [], params
    )
    assert rendered == '(?)'
