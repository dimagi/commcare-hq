import json
from unittest import expectedFailure

from django.http import QueryDict
from django.utils.safestring import mark_safe
from django.test import SimpleTestCase, TestCase

from dimagi.utils.dates import DateSpan

from corehq.apps.reports.generic import GenericTabularReport
from ..app_config import get_report_class

from ..generic import _sanitize_rows
from ...users.models import WebUser


class GenericTabularReportTests(SimpleTestCase):

    def test_strip_tags_html_bytestring(self):
        """
        _strip_tags should strip HTML tags
        """
        value = '<blink>182</blink>'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '182')

    def test_strip_tags_html_unicode(self):
        """
        _strip_tags should strip HTML tags from Unicode
        """
        value = '<blink>182</blink>'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '182')

    def test_strip_tags_passthru(self):
        """
        _strip_tags should allow non-basestring values to pass through
        """
        value = {'blink': 182}
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, {'blink': 182})

    @expectedFailure
    def test_strip_tags_expected_fail(self):
        """
        _strip_tags should not strip strings inside angle brackets, but does
        """
        value = '1 < 8 > 2'
        value = GenericTabularReport._strip_tags(value)
        self.assertEqual(value, '1 < 8 > 2')


class SanitizeRowTests(SimpleTestCase):
    def test_normal_output(self):
        rows = [['One']]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['One'])

    def test_escapes_rows(self):
        rows = [['<script>Hello</script>']]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['&lt;script&gt;Hello&lt;/script&gt;'])

    def test_does_not_escape_safe_text(self):
        rows = [[mark_safe('<div>Safe!</div>')]]  # nosec: test data

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['<div>Safe!</div>'])

    def test_handles_rows(self):
        rows = [
            ['One', 'Two'],
            ['Three', 'Four'],
            ['Five', 'Six']
        ]

        result = _sanitize_rows(rows)
        self.assertEqual(result[0], ['One', 'Two'])
        self.assertEqual(result[1], ['Three', 'Four'])
        self.assertEqual(result[2], ['Five', 'Six'])


class GetSerializableReportParameters(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(domain='test-domain', username='test-user')
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, deleted_by_domain='test-domain', deleted_by=None)
        cls.report = object.__new__(get_report_class('daily_form_stats'))
        GET_params = QueryDict('', mutable=True)
        GET_params.update({
            'emw': ['t__0', 't__5'],
            'sub_time': '',
            'startdate': '2022-03-20',
            'enddate': '2022-03-28'
        })
        cls.report_params = {
            'request': {
                'GET': GET_params,
                'META': {
                    'QUERY_STRING': '',
                    'PATH_INFO': '/a/practice-tracker/reports/export/daily_form_stats/'
                },
                'couch_user': cls.user._id,
                'can_access_all_locations': True
            },
            'request_params': {
                'sub_time': '',
                'startdate': '2022-03-20T00:00:00',
                'enddate': '2022-03-28T00:00:00'
            },
            'domain': 'practice-tracker',
            'context': {}
        }
        cls.report.set_report_parameters(cls.report_params)

    def test_returns_serializable_state(self):
        serializable_state = self.report.get_json_report_parameters()
        try:
            json.dumps(serializable_state)
        except TypeError:
            self.fail('Expected json serializable state.')

    def test_equivalent(self):
        serializable_state = self.report.get_json_report_parameters()
        self.assertEqual(serializable_state, self.report_params)

    def test_query_dict_elements_preserved_after_serializing(self):
        """
        QueryDict.dict() only includes 1 element per key which is what json.dumps() invokes
        """
        test_querydict = QueryDict('', mutable=True)
        test_querydict.update({'test-key': 'test-value-1'})
        test_querydict.update({'test-key': 'test-value-2'})
        expected_result = dict(test_querydict.lists())

        self.report_params['request']['GET'] = test_querydict
        self.report.set_report_parameters(self.report_params)

        serializable_state = self.report.get_json_report_parameters()
        serialized_state = json.dumps(serializable_state)
        state = json.loads(serialized_state)
        self.assertFalse(isinstance(state['request']['GET'], QueryDict))
        self.assertEqual(expected_result, state['request']['GET'])


class SetReportParametersTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(domain='test-domain', username='test-user')
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, deleted_by_domain='test-domain', deleted_by=None)
        cls.report = object.__new__(get_report_class('daily_form_stats'))

    def test_recreates_query_dict(self):
        test_querydict = QueryDict('', mutable=True)
        test_querydict.update({'test-key': 'test-value-1'})
        test_querydict.update({'test-key': 'test-value-2'})

        self.report.set_report_parameters({
            'request': {
                'GET': dict(test_querydict.lists()),
                'couch_user': self.user._id,
            },
            'request_params': {},
        })

        self.assertEqual(self.report.request.GET, test_querydict)
