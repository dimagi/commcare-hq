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
