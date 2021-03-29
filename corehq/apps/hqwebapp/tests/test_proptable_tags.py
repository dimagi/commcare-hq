import pytz
from django.test import SimpleTestCase, override_settings
from mock.mock import patch

from corehq.apps.hqwebapp.doc_info import DocInfo, get_commcareuser_url
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
        column = DisplayConfig(expr='colour', has_history=True)
        data = {'colour': 'red'}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'colour', 'name': 'colour', 'value': 'red', 'has_history': True}
        )

    def test_get_display_data_format(self):
        column = DisplayConfig(expr='colour', format="<b>{}</b>")
        data = {'colour': 'red'}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'colour', 'name': 'colour', 'value': '<b>red</b>', 'has_history': False}
        )

    def test_get_display_process_yesno(self):
        column = DisplayConfig(expr='big', process="yesno")
        data = {'big': True}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'big', 'name': 'big', 'value': 'yes', 'has_history': False}
        )

    @patch("corehq.apps.hqwebapp.templatetags.proptable_tags.get_doc_info_by_id")
    def test_get_display_process_docinfo(self, get_doc_info_by_id):
        get_doc_info_by_id.return_value = DocInfo(
            display="Bob",
            type_display="Mobile Worker",
            link="https://www.commcarehq.org/i_am_bob",
            is_deleted=False,
        )
        column = DisplayConfig(expr='bob', process="doc_info")
        data = {'bob': True, 'domain': 'bobs_domain'}
        expected_value = 'Mobile Worker\n<a href="https://www.commcarehq.org/i_am_bob">Bob</a>\n'
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'bob', 'name': 'bob', 'value': expected_value, 'has_history': False}
        )

    def test_get_display_process_date(self):
        column = DisplayConfig(expr='date', process="date")
        data = {'date': "2021-03-16T14:37:22Z"}
        expected_value = (
            "<time title='2021-03-16T14:37:22+00:00' datetime='2021-03-16T14:37:22+00:00'>"
            "Mar 16, 2021 14:37 UTC"
            "</time>"
        )
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'date', 'name': 'date', 'value': expected_value, 'has_history': False}
        )

    def test_get_display_process_timeago(self):
        column = DisplayConfig(expr='date', process="date", timeago=True)
        data = {'date': "2021-03-16T14:37:22Z"}
        expected_value = (
            "<time class='timeago' title='2021-03-16T14:37:22+00:00' datetime='2021-03-16T14:37:22+00:00'>"
            "Mar 16, 2021 14:37 UTC"
            "</time>"
        )
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'date', 'name': 'date', 'value': expected_value, 'has_history': False}
        )

    @override_settings(PHONE_TIMEZONES_HAVE_BEEN_PROCESSED=True)
    def test_get_display_process_phonetime(self):
        column = DisplayConfig(expr='date', process="date", is_phone_time=True)
        data = {'date': "2021-03-16T14:37:22Z"}
        expected_value = (
            "<time title='2021-03-16T16:37:22+02:00' datetime='2021-03-16T16:37:22+02:00'>"
            "Mar 16, 2021 16:37 SAST"
            "</time>"
        )
        self.assertEqual(
            get_display_data(data, column, timezone=pytz.timezone("Africa/Johannesburg")),
            {'expr': 'date', 'name': 'date', 'value': expected_value, 'has_history': False}
        )

    def test_get_display_data_blank(self):
        column = DisplayConfig(expr='not_prop')
        data = {'prop': True}
        self.assertEqual(
            get_display_data(data, column),
            {'expr': 'not_prop', 'name': 'not prop', 'value': '---', 'has_history': False}
        )
