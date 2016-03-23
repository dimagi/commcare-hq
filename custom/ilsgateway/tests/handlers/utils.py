from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.commtrack.models import CommtrackActionConfig
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, SQLLocation, LocationType
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.utils import make_loc
from custom.logistics.tests.test_script import TestScript
from custom.ilsgateway.models import ILSGatewayConfig
from custom.logistics.tests.utils import bootstrap_user
from casexml.apps.stock.models import DocDomainMapping

TEST_DOMAIN = 'ils-test-domain'


def create_products(cls, domain_name, codes):
    for code in codes:
        product = Product(domain=domain_name, name=code, code=code, unit='each')
        product.save()
        setattr(cls, code, product)


class ILSTestScript(TestScript):

    @classmethod
    def setUpClass(cls):
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        domain = prepare_domain(TEST_DOMAIN)
        mohsw = make_loc(code="moh1", name="Test MOHSW 1", type="MOHSW", domain=domain.name)

        msdzone = make_loc(code="msd1", name="MSD Zone 1", type="MSDZONE",
                           domain=domain.name, parent=mohsw)

        region = make_loc(code="reg1", name="Test Region 1", type="REGION",
                          domain=domain.name, parent=msdzone)

        cls.district = make_loc(code="dis1", name="Test District 1", type="DISTRICT",
                            domain=domain.name, parent=region)
        cls.district2 = make_loc(code="d10101", name="Test District 2", type="DISTRICT",
                                 domain=domain.name, parent=region)
        cls.district3 = make_loc(code="d10102", name="TESTDISTRICT", type="DISTRICT",
                                 domain=domain.name, parent=region)
        cls.facility = make_loc(code="loc1", name="Test Facility 1", type="FACILITY",
                            domain=domain.name, parent=cls.district, metadata={'group': 'A'})
        cls.facility_sp_id = cls.facility.sql_location.supply_point_id
        facility2 = make_loc(code="loc2", name="Test Facility 2", type="FACILITY",
                             domain=domain.name, parent=cls.district, metadata={'group': 'B'})
        cls.facility3 = make_loc(
            code="d31049", name="Test Facility 3", type="FACILITY", domain=domain.name, parent=cls.district,
            metadata={'group': 'C'}
        )
        cls.user1 = bootstrap_user(
            cls.facility, username='stella', domain=domain.name, home_loc='loc1', phone_number='5551234',
            first_name='stella', last_name='Test', language='sw'
        )
        bootstrap_user(facility2, username='bella', domain=domain.name, home_loc='loc2', phone_number='5555678',
                       first_name='bella', last_name='Test', language='sw')
        bootstrap_user(cls.district, username='trella', domain=domain.name, home_loc='dis1', phone_number='555',
                       first_name='trella', last_name='Test', language='sw')
        bootstrap_user(cls.district, username='msd_person', domain=domain.name, phone_number='111',
                       first_name='MSD', last_name='Person', user_data={'role': 'MSD'}, language='sw')

        for x in xrange(1, 4):
            bootstrap_user(
                cls.facility3,
                username='person{}'.format(x), domain=domain.name, phone_number=str(32346 + x),
                first_name='Person {}'.format(x), last_name='Person {}'. format(x), home_loc='d31049',
                language='sw'
            )
            bootstrap_user(
                cls.district2,
                username='dperson{}'.format(x), domain=domain.name, phone_number=str(32349 + x),
                first_name='dPerson {}'.format(x), last_name='dPerson {}'. format(x), home_loc='d10101',
                language='sw'
            )

        create_products(cls, domain.name, ["id", "dp", "fs", "md", "ff", "dx", "bp", "pc", "qi", "jd", "mc", "ip"])

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
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.sms_backend_mapping.delete()
        cls.sms_backend.delete()
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
    from corehq.apps.commtrack.tests.util import bootstrap_domain
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
    ils_config = ILSGatewayConfig(enabled=True, domain=domain.name, all_stock_data=True)
    ils_config.save()
    fields_definition = CustomDataFieldsDefinition.get_or_create(domain.name, 'LocationFields')
    fields_definition.fields.append(CustomDataField(
        slug='group',
        label='Group',
        is_required=False,
        choices=['A', 'B', 'C'],
        is_multiple_choice=False
    ))
    fields_definition.save()
    return domain


def add_products(sql_location, products_codes_list):
    sql_location.products = [
        SQLProduct.objects.get(domain=sql_location.domain, code=code)
        for code in products_codes_list
    ]
    sql_location.save()
