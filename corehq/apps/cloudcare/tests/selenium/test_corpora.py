"""
Tests for applications in the 'corpora' domain.

"""

from testcases import CloudCareTestCase
import random


class BasicTestTestCase(CloudCareTestCase):
    app_name = 'Basic Test'
    module_name = 'Basic Test'
    update_case_form = 'Update Case'
    close_case_form = 'Close Case'

    def _create_case(self):
        self.open_form('New Case')
        name = self.random_string()
        self.find_question('Enter your name').set_value(name)
        self.submit_form()

        return name

    def test_first_form(self):
        self.open_form('First Form')
        name = self.random_string()
        self.find_question('Enter your name').set_value(name)
        self.submit_form()
        self.assertNotIn(name, self.get_open_case_names())

    def test_new_case(self):
        name = self._create_case()
        self.assertIn(name, self.get_open_case_names())

    def test_update_case(self):
        colors = {'blue': 'Blue',
                  'brown': 'Brown',
                  'black': 'Black',
                  'green': 'Green'}

        name = self._create_case()
        color_val = random.choice(colors.keys())
        color_disp = colors[color_val]

        self.open_form('Update Case')
        self.enter_update_case(name)
        self.find_question('Select an eye colour').set_value(color_disp)
        self.submit_form()
        self.assertEqual(color_val, self.get_case_details(name)['Eye Colour'])

    def test_close_case(self):
        name = self._create_case()
        self.open_form('Close Case')
        self.enter_close_case(name)
        self.find_question('Reason for Closing').set_value('foo')
        self.submit_form()
        self.assertNotIn(name, self.get_open_case_names())
