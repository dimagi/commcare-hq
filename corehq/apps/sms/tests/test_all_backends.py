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

        self.unicel_backend = UnicelBackend(name='UNICEL', is_global=True)
        self.unicel_backend.save()

        self.mach_backend = MachBackend(name='MACH', is_global=True)
        self.mach_backend.save()

        self.tropo_backend = TropoBackend(name='TROPO', is_global=True)
        self.tropo_backend.save()

        self.http_backend = HttpBackend(name='HTTP', is_global=True)
        self.http_backend.save()

        self.telerivet_backend = TelerivetBackend(name='TELERIVET', is_global=True)
        self.telerivet_backend.save()

        self.test_backend = TestSMSBackend(name='TEST', is_global=True)
        self.test_backend.save()

        self.grapevine_backend = GrapevineBackend(name='GRAPEVINE', is_global=True)
        self.grapevine_backend.save()

        self.twilio_backend = TwilioBackend(name='TWILIO', is_global=True)
        self.twilio_backend.save()

        self.megamobile_backend = MegamobileBackend(name='MEGAMOBILE', is_global=True)
        self.megamobile_backend.save()

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
        self._test_outbound_backend(self.unicel_backend, 'unicel test')
        self._test_outbound_backend(self.mach_backend, 'mach test')
        self._test_outbound_backend(self.tropo_backend, 'tropo test')
        self._test_outbound_backend(self.http_backend, 'http test')
        self._test_outbound_backend(self.telerivet_backend, 'telerivet test')
        self._test_outbound_backend(self.test_backend, 'test test')
        self._test_outbound_backend(self.grapevine_backend, 'grapevine test')
        self._test_outbound_backend(self.twilio_backend, 'twilio test')
        self._test_outbound_backend(self.megamobile_backend, 'megamobile test')

    def tearDown(self):
        backend_api.TEST = False
        self.domain_obj.delete()
        self.unicel_backend.delete()
        self.mach_backend.delete()
        self.tropo_backend.delete()
        self.http_backend.delete()
        self.telerivet_backend.delete()
        self.test_backend.delete()
        self.grapevine_backend.delete()
        self.twilio_backend.delete()
        self.megamobile_backend.delete()
        super(AllBackendTest, self).tearDown()
