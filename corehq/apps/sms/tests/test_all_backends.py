from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from django.test.client import Client
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import send_sms
from corehq.apps.sms.models import SMS
from corehq.apps.sms import mixin as backend_api
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.messaging.smsbackends.unicel.api import UnicelBackend
from corehq.messaging.smsbackends.mach.api import MachBackend
from corehq.messaging.smsbackends.tropo.api import TropoBackend
from corehq.messaging.smsbackends.http.api import HttpBackend
from corehq.messaging.smsbackends.telerivet.models import TelerivetBackend
from corehq.apps.sms.test_backend import TestSMSBackend
from corehq.messaging.smsbackends.grapevine.api import GrapevineBackend
from corehq.messaging.smsbackends.twilio.models import TwilioBackend
from corehq.messaging.smsbackends.megamobile.api import MegamobileBackend


class AllBackendTest(BaseSMSTest):
    def setUp(self):
        super(AllBackendTest, self).setUp()
        backend_api.TEST = True

        self.domain_obj = Domain(name='all-backend-test')
        self.domain_obj.save()
        self.create_account_and_subscription(self.domain_obj.name)
        self.domain_obj = Domain.get(self.domain_obj._id)

        self.twilio_backend = TwilioBackend(name='TWILIO', is_global=True)
        self.twilio_backend.save()

    def _test_outbound_backend(self, backend, msg_text):
        from corehq.apps.sms.tests import BackendInvocationDoc
        self.domain_obj.default_sms_backend_id = backend._id
        self.domain_obj.save()

        send_sms(self.domain_obj.name, None, '+99912345', msg_text)
        sms = SMS.objects.get(
            domain=self.domain_obj.name,
            direction='O',
            text=msg_text
        )

        invoke_doc_id = '%s-%s' % (backend.__class__.__name__, json_format_datetime(sms.date))
        invoke_doc = BackendInvocationDoc.get(invoke_doc_id)
        self.assertIsNotNone(invoke_doc)

    def test_outbound_sms(self):
        self._test_outbound_backend(self.twilio_backend, 'twilio test')

    def tearDown(self):
        backend_api.TEST = False
        self.domain_obj.delete()
        self.twilio_backend.delete()
        super(AllBackendTest, self).tearDown()
