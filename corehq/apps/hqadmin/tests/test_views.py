from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch, Mock
import os

from django.http import HttpResponse
from django.test import SimpleTestCase
from lxml import etree

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqadmin.views.users import AdminRestoreView


class AdminRestoreViewTests(TestXmlMixin, SimpleTestCase):
    root = os.path.dirname(__file__)
    file_path = ['data']
    maxDiff = None

    def test_bad_restore(self):
        user = Mock()
        user.domain = None
        app_id = None
        request = Mock()
        request.GET = {}
        request.openrosa_headers = {}
        timing_context = Mock()
        timing_context.to_list.return_value = []
        with patch('corehq.apps.hqadmin.views.users.get_restore_response',
                   return_value=(HttpResponse('bad response', status=500), timing_context)):

            view = AdminRestoreView(user=user, app_id=app_id, request=request)
            context = view.get_context_data(foo='bar', view='AdminRestoreView')
            self.assertEqual(context, {
                'foo': 'bar',
                'view': 'AdminRestoreView',
                'payload': '<error>Unexpected restore response 500: bad response. If you believe this is a bug '
                           'please report an issue.</error>\n',
                'status_code': 500,
                'timing_data': [],
                'hide_xml': False,
            })

    def test_admin_restore_counts(self):
        xml_payload = etree.fromstring(self.get_xml('restore'))
        self.assertEqual(AdminRestoreView.get_stats_from_xml(xml_payload), {
            'restore_id': '02bbfb3ea17711e8adb9bc764e203eaf',
            'num_cases': 2,
            'num_locations': 7,
            'num_v1_reports': 2,
            'num_v2_reports': 2,
            'case_type_counts': {},
            'location_type_counts': {
                'country': 1,
                'state': 1,
                'county': 1,
                'city': 1,
                'neighborhood': 3,
            },
            'v1_report_row_counts': {
                'e009c3dc89b0250a8accd09b9641c3250f4e38d0--0dc41ff3e342d3ac94c06bb5c6cdd416': 3,
                '42dc83c562a474b7e5faba4fc3190ca37bd4777f--f1761733213601f7f77defc3bc2e2c87': 3,
            },
            'v2_report_row_counts': {
                'commcare-reports:e009c3dc89b0250a8accd09b9641c3250f4e38d0--0dc41ff3e342d3ac94c06bb5c6cdd416': 3,
                'commcare-reports:42dc83c562a474b7e5faba4fc3190ca37bd4777f--f1761733213601f7f77defc3bc2e2c87': 3,
            },
            'num_ledger_entries': 0,
        })
