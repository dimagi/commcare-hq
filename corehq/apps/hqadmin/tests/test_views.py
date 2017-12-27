from __future__ import absolute_import
from django.http import HttpResponse
from django.test import SimpleTestCase
from mock import patch, Mock

from corehq.apps.hqadmin.views import AdminRestoreView


class AdminRestoreViewTests(SimpleTestCase):

    def test_get_context_data(self):
        user = Mock()
        user.domain = None
        app_id = None
        request = Mock()
        request.GET = {}
        request.openrosa_headers = {}
        timing_context = Mock()
        timing_context.to_list.return_value = []
        with patch('corehq.apps.hqadmin.views.get_restore_response',
                   return_value=(HttpResponse('bad response', status=500), timing_context)):

            view = AdminRestoreView(user=user, app_id=app_id, request=request)
            context = view.get_context_data(foo='bar', view='AdminRestoreView')
            self.assertEqual(context, {
                'foo': 'bar',
                'view': 'AdminRestoreView',
                'payload': '<error>Unexpected restore response 500: bad response. If you believe this is a bug '
                           'please report an issue.</error>\n',
                'restore_id': None,
                'status_code': 500,
                'timing_data': [],
                'num_cases': 0,
                'num_locations': 0,
                'num_reports': 0,
                'hide_xml': False,
                'case_type_counts': {},
                'location_type_counts': {},
                'report_row_counts': {},
                'num_ledger_entries': 0,
            })
