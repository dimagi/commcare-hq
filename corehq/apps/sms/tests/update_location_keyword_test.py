from django.test.testcases import TestCase
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription, \
    SubscriptionAdjustment
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, LocationType
from corehq.apps.sms.api import incoming
from corehq.apps.sms.messages import get_message
from corehq.apps.sms.mixin import BackendMapping
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import create_mobile_worker
from corehq.apps.users.models import CommCareUser
from corehq.messaging.smsbackends.test.api import TestSMSBackend
import corehq.apps.sms.messages as messages


class UpdateLocationKeywordTest(TestCase):

    def _get_last_outbound_message(self):
        return SMS.objects.filter(domain=self.domain, direction='O').latest('date').text

    @classmethod
    def setUpClass(cls):
        super(UpdateLocationKeywordTest, cls).setUpClass()
        cls.domain = "opt-test"

        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        generator.instantiate_accounting_for_tests()
        cls.account = BillingAccount.get_or_create_account_by_domain(
            cls.domain_obj.name,
            created_by="automated-test",
        )[0]
        plan = DefaultProductPlan.get_default_plan_by_domain(
            cls.domain_obj, edition=SoftwarePlanEdition.ADVANCED
        )
        cls.subscription = Subscription.new_domain_subscription(
            cls.account,
            cls.domain_obj.name,
            plan
        )
        cls.subscription.is_active = True
        cls.subscription.save()

        cls.backend = TestSMSBackend(is_global=True)
        cls.backend.save()

        cls.backend_mapping = BackendMapping(
            is_global=True,
            prefix="*",
            backend_id=cls.backend._id,
        )
        cls.backend_mapping.save()

        cls.user = create_mobile_worker(cls.domain, 'test', '*****', ['4444'])

        cls.location_type = LocationType.objects.create(
            domain=cls.domain,
            name='test'
        )

        cls.location = Location(
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
        cls.user.delete()
        cls.backend_mapping.delete()
        cls.backend.delete()
        cls.domain_obj.delete()

        SubscriptionAdjustment.objects.all().delete()
        cls.subscription.delete()
        cls.account.delete()
