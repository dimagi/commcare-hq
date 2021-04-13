from datetime import date, datetime
from django.test import SimpleTestCase

from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data, _to_html


class CaseDisplayDataTest(SimpleTestCase):

    def test_get_display_data_name(self):
        column = {
            'name': 'favorite color',
            'expr': 'color'
        }
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'color', 'name': 'favorite color', 'value': 'red', 'has_history': False})

    def test_get_display_data_no_name(self):
        column = {
            'expr': 'color'
        }
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'color', 'name': 'color', 'value': 'red', 'has_history': False})

    def test_get_display_data_function(self):
        get_color = lambda x: x['color']
        column = {
            'name': 'favorite color',
            'expr': get_color,
        }
        data = {
            'color': 'red'
        }
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'favorite color', 'name': 'favorite color', 'value': 'red', 'has_history': False}
        )

    def test_get_display_data_history(self):
        column = {'expr': 'colour', 'has_history': True}
        data = {'colour': 'red'}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'colour', 'name': 'colour', 'value': 'red', 'has_history': True}
        )


class ToHTMLTest(SimpleTestCase):
    def test_handles_single_value(self):
        self.assertEqual(_to_html('value'), 'value')

    def test_converts_none_to_dashes(self):
        self.assertEqual(_to_html(None), '---')

    def test_single_values_are_escaped(self):
        self.assertEqual(_to_html('va<lue'), 'va&lt;lue')

    def test_handles_list(self):
        result = _to_html(['one', 'two', 'three'], key='test_list')
        self.assertEqual(result,
            "<dl>"
            "<dt>test_list</dt><dd>one</dd>"
            "<dt>test_list</dt><dd>two</dd>"
            "<dt>test_list</dt><dd>three</dd>"
            "</dl>")

    def test_list_key_and_value_are_escaped(self):
        result = _to_html(['va<lue'], key='ke>y')
        self.assertEqual(result,
            "<dl>"
            "<dt>ke&gt;y</dt><dd>va&lt;lue</dd>"
            "</dl>")

    def test_handles_dict(self):
        result = _to_html({'a': 'one', 'b': 'two'}, key='test_dict')
        self.assertEqual(result,
            "<dl class='well'>"
            "<dt>a</dt><dd>one</dd>"
            "<dt>b</dt><dd>two</dd>"
            "</dl>")

    def test_dict_key_and_values_are_escaped(self):
        result = _to_html({'ke>y': 'va<lue'})
        self.assertEqual(result,
            "<dl class='well'>"
            "<dt>ke&gt;y</dt><dd>va&lt;lue</dd>"
            "</dl>")

    def test_handles_date(self):
        result = _to_html(date(2020, 5, 25))
        self.assertEqual(result, "<time  title='2020-05-25' datetime='2020-05-25'>May 25, 2020</time>")

    def test_handles_datetime(self):
        result = _to_html(datetime(2020, 5, 25, 2, 12, 10, 100))
        self.assertEqual(result,
            "<time  title='2020-05-25T02:12:10.000100'"
            " datetime='2020-05-25T02:12:10.000100'>May 25, 2020 02:12 </time>")
