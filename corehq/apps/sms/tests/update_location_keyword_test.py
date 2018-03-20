from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.testcases import TestCase
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import make_location, LocationType
from corehq.apps.sms.api import incoming
from corehq.apps.sms.messages import get_message
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser
import corehq.apps.sms.messages as messages


def create_mobile_worker(domain, username, password, phone_number, save_vn=True):
    user = CommCareUser.create(domain, username, password, phone_number=phone_number)
    if save_vn:
        entry = user.get_or_create_phone_entry(phone_number)
        entry.set_two_way()
        entry.set_verified()
        entry.save()
    return user


class UpdateLocationKeywordTest(TestCase, DomainSubscriptionMixin):

    def _get_last_outbound_message(self):
        return SMS.objects.filter(domain=self.domain, direction='O').latest('date').text

    @classmethod
    def setUpClass(cls):
        super(UpdateLocationKeywordTest, cls).setUpClass()
        cls.domain = "opt-test"

        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        cls.setup_subscription(cls.domain_obj.name, SoftwarePlanEdition.ADVANCED)

        cls.backend, cls.backend_mapping = setup_default_sms_test_backend()

        cls.user = create_mobile_worker(cls.domain, 'test', '*****', '4444')

        cls.location_type = LocationType.objects.create(
            domain=cls.domain,
            name='test'
        )

        cls.location = make_location(
            domain=cls.domain,
            name='test',
            site_code='site_code',
            location_type='test'
        )
        cls.location.save()

    def test_message_without_keyword(self):
        incoming('4444', '#update', 'TEST')
        self.assertEqual(self._get_last_outbound_message(), get_message(messages.MSG_UPDATE))

    def test_with_invalid_action(self):
        incoming('4444', '#update notexists', 'TEST')
        self.assertEqual(self._get_last_outbound_message(), get_message(messages.MSG_UPDATE_UNRECOGNIZED_ACTION))

    def test_message_without_site_code(self):
        incoming('4444', '#update location', 'TEST')
        self.assertEqual(self._get_last_outbound_message(), get_message(messages.MSG_UPDATE_LOCATION_SYNTAX))

    def test_message_with_invalid_site_code(self):
        incoming('4444', '#update location notexists', 'TEST')
        self.assertEqual(
            self._get_last_outbound_message(),
            get_message(messages.MSG_UPDATE_LOCATION_SITE_CODE_NOT_FOUND, context=['notexists'])
        )

    def test_valid_message(self):
        incoming('4444', '#update location site_code', 'TEST')
        self.assertEqual(self._get_last_outbound_message(), get_message(messages.MSG_UPDATE_LOCATION_SUCCESS))
        user = CommCareUser.get(docid=self.user.get_id)
        self.assertEqual(user.location_id, self.location.get_id)

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(cls.domain)
        cls.user.delete()
        cls.backend_mapping.delete()
        cls.backend.delete()
        cls.domain_obj.delete()

        cls.teardown_subscription()

        super(UpdateLocationKeywordTest, cls).tearDownClass()
