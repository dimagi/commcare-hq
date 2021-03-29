from django.test import SimpleTestCase

from corehq.apps.hqwebapp.templatetags.proptable_tags import get_display_data, DisplayConfig


class CaseDisplayDataTest(SimpleTestCase):

    def test_get_display_data_name(self):
        column = DisplayConfig(name='favorite color', expr='color')
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'color', 'name': 'favorite color', 'value': 'red', 'has_history': False})

    def test_get_display_data_no_name(self):
        column = DisplayConfig(expr='color')
        data = {
            'color': 'red'
        }
        self.assertEqual(get_display_data(data, column),
                         {'expr': 'color', 'name': 'color', 'value': 'red', 'has_history': False})

    def test_get_display_data_function(self):
        get_color = lambda x: x['color']
        column = DisplayConfig(name='favorite color', expr=get_color)
        data = {
            'color': 'red'
        }
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'favorite color', 'name': 'favorite color', 'value': 'red', 'has_history': False}
        )

    def test_get_display_data_history(self):
        column = DisplayConfig(expr='color', has_history=True)
        data = {'colour': 'red'}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'colour', 'name': 'colour', 'value': 'red', 'has_history': True}
        )

    def test_get_display_data_format(self):
        column = DisplayConfig(expr='color', format="<b>{}</b>")
        data = {'colour': 'red'}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'colour', 'name': 'colour', 'value': '<b>red</b>'}
        )

    def test_get_display_process(self):
        column = DisplayConfig(expr='big', process="yesno")
        data = {'big': True}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'big', 'name': 'big', 'value': 'yes'}
        )
