from corehq.apps.domain.shortcuts import create_domain
from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.users.models import WebUser

from ..interface import EnterpriseSMSBillablesInterface


class TestEnterpriseSMSBillablesInterface(TestCase):

    def test_headers(self):
        interface = self.create_interface()
        test_headers = [['Date of Message', 'Project Space', 'Direction', 'SMS parts', 'Gateway',
            'Gateway Charge', 'Usage Charge', 'Total Charge', 'Message Log ID', 'Is Valid?', 'Date Created']]
        self.assertEqual(interface.headers.as_export_table, test_headers)

    def create_interface(self):
        request = RequestFactory().get('')
        user = WebUser()
        request.couch_user = user
        return EnterpriseSMSBillablesInterface(request)
