"""
Submit a form from a rendered page in a test, the way a browser would.
"""
from html.parser import HTMLParser

import lxml.html
from django.test import Client


def csrf_client(username, password):
    """A test client that enforces CSRF checks, logged in as ``username``"""
    client = Client(enforce_csrf_checks=True)
    assert client.login(username=username, password=password)
    return client


def submit_form(client, page, button_text, within=None):
    """
    Click the submit button labelled ``button_text`` on ``page``, a response.

    This tests the markup as well as the view: the button must belong to a
    form (directly or through its ``form`` attribute) that is not nested in
    another form, and the form's action, method and fields (including the
    CSRF token) must be what the view needs.

    :param client: A client from ``csrf_client()``, so that a missing CSRF
        token fails the request.
    :param within: The id of an element to look for the button in, when the
        page has more than one button with that label.
    """
    form = get_button_form(page.content.decode(), button_text, within)
    assert form.method.lower() == 'post', f'{button_text!r} submits a {form.method} form'
    return client.post(form.action, dict(form.form_values()))


def get_button_form(html, button_text, within=None):
    doc = lxml.html.fromstring(html)
    scope = doc if within is None else doc.get_element_by_id(within)
    buttons = scope.xpath('.//button[normalize-space()=$text]', text=button_text)
    assert len(buttons) == 1, f'expected one {button_text!r} button, found {len(buttons)}'
    button = buttons[0]
    assert button.get('type', 'submit') == 'submit', f'{button_text!r} is not a submit button'
    if button.get('form'):
        form = doc.get_element_by_id(button.get('form'), None)
    else:
        form = next(button.iterancestors('form'), None)
    assert form is not None and form.tag == 'form', f'{button_text!r} does not belong to a form'
    # lxml closes an open form when it meets a nested one, whereas browsers
    # ignore the nested form tag and submit the outer form instead
    assert form.sourceline not in _nested_form_lines(html), \
        f'{button_text!r} is in a form nested in another form (line {form.sourceline})'
    return form


def _nested_form_lines(html):
    parser = _FormNestingParser()
    parser.feed(html)
    parser.close()
    return parser.nested_lines


class _FormNestingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested_lines = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            if self.depth:
                self.nested_lines.add(self.getpos()[0])
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == 'form' and self.depth:
            self.depth -= 1
