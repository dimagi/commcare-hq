import pytest

from corehq.tests.util.forms import get_button_form


def test_button_inside_form():
    form = _get_form('<form method="post" action="/go/"><input name="a" value="1"><button>Go</button></form>')
    assert form.action == '/go/'
    assert dict(form.form_values()) == {'a': '1'}


def test_button_with_form_attribute():
    form = _get_form(
        '<form action="/other/"><button form="target">Go</button></form>'
        '<form id="target" method="post" action="/go/"></form>'
    )
    assert form.action == '/go/'


def test_button_label_ignores_icons_and_whitespace():
    form = _get_form('<form action="/go/"><button>\n  <i class="fa fa-envelope"></i>\n  Go\n</button></form>')
    assert form.action == '/go/'


def test_unrelated_nested_form_is_ignored():
    form = _get_form(
        '<form action="/outer/">\n<form action="/inner/"></form></form>\n'
        '<form action="/go/"><button>Go</button></form>'
    )
    assert form.action == '/go/'


def test_button_within_element():
    form = get_button_form(
        '<form action="/one/"><button>Go</button></form>'
        '<div id="two"><form action="/two/"><button>Go</button></form></div>',
        'Go',
        within='two',
    )
    assert form.action == '/two/'


@pytest.mark.parametrize('html, message', [
    ('<form action="/go/"></form>', 'found 0'),
    ('<form><button>Go</button></form><form><button>Go</button></form>', 'found 2'),
    ('<a href="/go/">Go</a><button>Go</button>', 'does not belong to a form'),
    ('<form><button type="button">Go</button></form>', 'not a submit button'),
    ('<button form="missing">Go</button>', 'does not belong to a form'),
    ('<form action="/outer/">\n<form action="/go/"><button>Go</button></form></form>', 'nested in another form'),
])
def test_invalid_markup(html, message):
    with pytest.raises(AssertionError, match=message):
        _get_form(html)


def _get_form(body):
    return get_button_form(f'<html><body>{body}</body></html>', 'Go')
