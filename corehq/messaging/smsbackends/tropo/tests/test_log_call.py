from __future__ import absolute_import
from __future__ import unicode_literals
import corehq.apps.ivr.tests.util as util
from corehq.messaging.smsbackends.tropo.models import SQLTropoBackend
from django.test import Client
import json


class TropoLogCallTestCase(util.LogCallTestCase):

    @classmethod
    def setUpClass(cls):
        super(TropoLogCallTestCase, cls).setUpClass()
        cls.tropo_backend = SQLTropoBackend.objects.create(
            name='TROPO',
            is_global=True,
            hq_api_id=SQLTropoBackend.get_api_id()
        )

    @classmethod
    def tearDownClass(cls):
        cls.tropo_backend.delete()
        super(TropoLogCallTestCase, cls).tearDownClass()

    def simulate_inbound_call(self, phone_number):
        return Client().post(
            '/tropo/ivr/%s/' % self.tropo_backend.inbound_api_key,
            json.dumps({'session': {'from': {'id': phone_number}}}),
            content_type='application/json'
        )

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '{"tropo": [{"reject": {}}]}')
