from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.commtrack.models import CommtrackActionConfig
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, SQLLocation, LocationType
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.sms.mixin import MobileBackend
from corehq.apps.users.models import CommCareUser
from custom.logistics.tests.test_script import TestScript
from corehq.apps.commtrack.tests.util import make_loc, TEST_BACKEND
from corehq.apps.sms.backend import test
from custom.ilsgateway.models import ILSGatewayConfig
from custom.logistics.tests.utils import bootstrap_user
from casexml.apps.stock.models import DocDomainMapping

TEST_DOMAIN = 'ils-test-domain'


class ILSTestScript(TestScript):

    @classmethod
    def setUpClass(cls):
        domain = prepare_domain(TEST_DOMAIN)
        mohsw = make_loc(code="moh1", name="Test MOHSW 1", type="MOHSW", domain=domain.name)

        msdzone = make_loc(code="msd1", name="MSD Zone 1", type="MSDZONE",
                          domain=domain.name, parent=mohsw)

        region = make_loc(code="reg1", name="Test Region 1", type="REGION",
                          domain=domain.name, parent=msdzone)

        district = make_loc(code="dis1", name="Test District 1", type="DISTRICT",
                            domain=domain.name, parent=region)
        facility = make_loc(code="loc1", name="Test Facility 1", type="FACILITY",
                            domain=domain.name, parent=district)
        facility2 = make_loc(code="loc2", name="Test Facility 2", type="FACILITY",
                             domain=domain.name, parent=district)
        test.bootstrap(TEST_BACKEND, to_console=True)
        bootstrap_user(facility, username='stella', domain=domain.name, home_loc='loc1', phone_number='5551234',
                       first_name='stella', last_name='Test')
        bootstrap_user(facility2, username='bella', domain=domain.name, home_loc='loc2', phone_number='5555678',
                       first_name='bella', last_name='Test')
        bootstrap_user(district, username='trella', domain=domain.name, home_loc='dis1', phone_number='555',
                       first_name='trella', last_name='Test')
        bootstrap_user(district, username='msd_person', domain=domain.name, phone_number='111',
                       first_name='MSD', last_name='Person', user_data={'role': 'MSD'})

        p = Product(domain=domain.name, name='Jadelle', code='jd', unit='each')
        p.save()
        p2 = Product(domain=domain.name, name='Mc', code='mc', unit='each')
        p2.save()

    def setUp(self):
        self.domain = Domain.get_by_name(TEST_DOMAIN)
        self.loc1 = Location.by_site_code(TEST_DOMAIN, 'loc1')
        self.loc2 = Location.by_site_code(TEST_DOMAIN, 'loc2')
        self.dis = Location.by_site_code(TEST_DOMAIN, 'dis1')
        self.user_fac1 = CommCareUser.get_by_username('stella')
        self.user_fac2 = CommCareUser.get_by_username('bella')
        self.user_dis = CommCareUser.get_by_username('trella')
        self.msd_user = CommCareUser.get_by_username('msd_person')

    @classmethod
    def tearDownClass(cls):
        MobileBackend.load_by_name(TEST_DOMAIN, TEST_BACKEND).delete()
        CommCareUser.get_by_username('stella').delete()
        CommCareUser.get_by_username('bella').delete()
        CommCareUser.get_by_username('trella').delete()
        CommCareUser.get_by_username('msd_person').delete()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()
        SQLProduct.objects.all().delete()
        ILSGatewayConfig.for_domain(TEST_DOMAIN).delete()
        DocDomainMapping.objects.all().delete()
        Location.by_site_code(TEST_DOMAIN, 'loc1').delete()
        Location.by_site_code(TEST_DOMAIN, 'loc2').delete()
        Location.by_site_code(TEST_DOMAIN, 'dis1').delete()
        Location.by_site_code(TEST_DOMAIN, 'reg1').delete()
        Location.by_site_code(TEST_DOMAIN, 'moh1').delete()
        SQLLocation.objects.all().delete()
        generator.delete_all_subscriptions()
        Domain.get_by_name(TEST_DOMAIN).delete()


def prepare_domain(domain_name):
    from corehq.apps.commtrack.tests import bootstrap_domain
    domain = bootstrap_domain(domain_name)
    previous = None
    for name, administrative in [
        ("MOHSW", True),
        ("MSDZONE", True),
        ("REGION", True),
        ("DISTRICT", True),
        ("FACILITY", False)
    ]:
        previous, _ = LocationType.objects.get_or_create(
            domain=domain_name,
            name=name,
            parent_type=previous,
            administrative=administrative,
        )

    generator.instantiate_accounting_for_tests()
    account = BillingAccount.get_or_create_account_by_domain(
        domain.name,
        created_by="automated-test",
    )[0]
    plan = DefaultProductPlan.get_default_plan_by_domain(
        domain, edition=SoftwarePlanEdition.ADVANCED
    )
    commtrack = domain.commtrack_settings
    commtrack.actions.append(
        CommtrackActionConfig(action='receipts',
                              keyword='delivered',
                              caption='Delivered')
    )
    commtrack.save()
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
