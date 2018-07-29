from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from mock import patch

from corehq.apps.data_analytics.gir_generator import GIRTableGenerator
from corehq.apps.domain.models import Domain


class GirTest(TestCase):

    def _fake_device_data(self, *args, **kwargs):
        return {
            'cloudcare': 25,
            'commconnect': 3,
            'phone1': 5,
            'phone2': 5,
            'phone3': 5,
            'phone4': 5,
            'phone5': 5,
            'phone': 7
        }

    def test_max_device_id(self):
        # test to make sure max device is properly calculated, and that phones are properly combined
        with patch('corehq.apps.data_analytics.gir_generator.get_domain_device_breakdown_es',
                   new=self._fake_device_data):
            max_device = GIRTableGenerator.get_max_device(Domain(name='dummy'), 'month')
            self.assertEqual(max_device, 'mobile')
