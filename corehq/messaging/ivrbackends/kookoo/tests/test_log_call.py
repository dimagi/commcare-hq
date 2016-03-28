import corehq.apps.ivr.tests.util as util
from corehq.messaging.ivrbackends.kookoo.models import SQLKooKooBackend
from django.test import Client


class KooKooLogCallTestCase(util.LogCallTestCase):
    @property
    def phone_number(self):
        return '9100000000'

    def setUp(self):
        super(KooKooLogCallTestCase, self).setUp()
        self.backend = SQLKooKooBackend(
            backend_type=SQLKooKooBackend.IVR,
            name='MOBILE_BACKEND_KOOKOO',
            is_global=True,
            hq_api_id=SQLKooKooBackend.get_api_id()
        )
        self.backend.save()

    def tearDown(self):
        super(KooKooLogCallTestCase, self).tearDown()
        self.backend.delete()

    def simulate_inbound_call(self, phone_number):
        phone_number = '0%s' % phone_number[2:]
        return Client().get('/kookoo/ivr/?cid=%s&sid=xyz&event=NewCall' % phone_number)

    def check_response(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, '<response sid="xyz"><hangup/></response>')
