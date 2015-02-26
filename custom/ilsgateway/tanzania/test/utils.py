from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from corehq.apps.locations.schema import LocationType
from corehq.apps.users.models import CommCareUser
from custom.logistics.test.test_script import TestScript
from corehq.apps.commtrack.tests.util import make_loc, TEST_BACKEND
from corehq.apps.sms.backend import test
from custom.ilsgateway.models import ILSGatewayConfig
from custom.logistics.test.utils import bootstrap_user

TEST_DOMAIN = 'ils-test-domain'


class ILSTestScript(TestScript):

    @classmethod
    def setUpClass(cls):
        domain = prepare_domain(TEST_DOMAIN)
        loc = make_loc(code="loc1", name="Test Facility 1", type="facility", domain=domain.name)
        test.bootstrap(TEST_BACKEND, to_console=True)
        bootstrap_user(loc, username='stella', domain=domain.name, home_loc='loc1')

    def setUp(self):
        self.domain = Domain.get_by_name(TEST_DOMAIN)
        self.loc = Location.by_site_code(TEST_DOMAIN, 'loc1')
        self.user = CommCareUser.get_by_username('stella')


def prepare_domain(domain_name):
    from corehq.apps.commtrack.tests import bootstrap_domain
    domain = bootstrap_domain(domain_name)
    domain.location_types = [
        LocationType(name="mohsw", allowed_parents=[""],
                     administrative=True),
        LocationType(name="region", allowed_parents=["mohsw"],
                     administrative=True),
        LocationType(name="district", allowed_parents=["region"],
                     administrative=True),
        LocationType(name="facility", allowed_parents=["district"],
                     administrative=False)
    ]
    domain.save()
    generator.instantiate_accounting_for_tests()
    account = BillingAccount.get_or_create_account_by_domain(
        domain.name,
        created_by="automated-test",
    )[0]
    plan = DefaultProductPlan.get_default_plan_by_domain(
        domain, edition=SoftwarePlanEdition.ADVANCED
    )
    subscription = Subscription.new_domain_subscription(
        account,
        domain.name,
        plan
    )
    subscription.is_active = True
    subscription.save()
    ils_config = ILSGatewayConfig(enabled=True, domain=domain.name)
    ils_config.save()
    return domain