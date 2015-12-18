from corehq.apps.ivr.tests.util import LogCallTestCase
from corehq.messaging.ivrbackends.kookoo.models import KooKooBackend
from django.test import Client


class KooKooLogCallTestCase(LogCallTestCase):
    @property
    def phone_number(self):
        return '9100000000'

    def setUp(self):
        super(KooKooLogCallTestCase, self).setUp()
        self.backend = KooKooBackend(
            _id='MOBILE_BACKEND_KOOKOO',
            name='MOBILE_BACKEND_KOOKOO',
            is_global=True
        )
        self.backend.save()

    def tearDown(self):
        super(KooKooLogCallTestCase, self).tearDown()
        self.backend.delete()

    def simulate_inbound_call(self, phone_number):
        phone_number = '0%s' % phone_number[2:]
        return Client().get('/kookoo/ivr/?cid=%s&sid=xyz&event=NewCall' % phone_number)

    def check_response(self, response):
        self.assertEqual(response.content, '<response sid="xyz"><hangup/></response>')
