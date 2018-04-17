from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data


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
                         {'expr': 'color', 'name': 'favorite color', 'value': 'red', 'info_url': None})

    def test_get_display_data_no_name(self):
        column = {
            'expr': 'color'
        }
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'color', 'name': 'color', 'value': 'red', 'info_url': None})

    def test_get_display_data_function(self):
        get_color = lambda x: x['color']
        column = {
            'name': 'favorite color',
            'expr': get_color,
        }
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'favorite color', 'name': 'favorite color', 'value': 'red', 'info_url': None})

    def test_get_display_data_info_url(self):
        column = {'expr': 'colour'}
        data = {'colour': 'red'}
        info_url = "/stuff/__placeholder__/other_stuff"
        self.assertEqual(
            get_display_data(data, column, info_url=info_url),
            {'expr': 'colour', 'name': 'colour', 'value': 'red', 'info_url': '/stuff/colour/other_stuff'}
        )
