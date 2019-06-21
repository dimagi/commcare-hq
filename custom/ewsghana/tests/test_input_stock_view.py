from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal
from django.urls import reverse
from django.test import TestCase
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.users.models import WebUser, UserRole
from django.test.client import Client
from custom.ewsghana.models import EWSExtension
from custom.ewsghana.reports.specific_reports.stock_status_report import StockStatus
from custom.ewsghana.utils import make_url
from . import test_utils

TEST_DOMAIN = 'ewsghana-test-input-stock'


class TestInputStockView(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super(TestInputStockView, cls).setUpClass()
        cls.domain = initial_bootstrap(TEST_DOMAIN)

        cls.setup_subscription(TEST_DOMAIN, SoftwarePlanEdition.ENTERPRISE)

        test_utils.prepare_commtrack_config(TEST_DOMAIN)
        test_utils.prepare_custom_fields(TEST_DOMAIN)
        test_utils.create_or_edit_roles(TEST_DOMAIN)
        test_utils.create_test_products(TEST_DOMAIN)
        test_utils.create_test_locations(TEST_DOMAIN)

        cls.test_facility3 = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='tsactive')
        cls.testregion2 = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='testregion2')
        cls.rsp = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='rsp')
        cls.test_district = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='testdistrict')

        cls.username1 = 'ews_user1'
        cls.password1 = 'dummy'
        cls.web_user1 = WebUser.create(TEST_DOMAIN, cls.username1, cls.password1)

        cls.web_user1.eula.signed = True
        cls.web_user1.save()

        cls.username2 = 'ews_user2'
        cls.password2 = 'dummy'
        cls.web_user2 = WebUser.create(TEST_DOMAIN, cls.username2, cls.password2)
        cls.web_user2.get_domain_membership(TEST_DOMAIN).location_id = cls.test_facility3.location_id

        cls.web_user2.eula.signed = True
        cls.web_user2.save()

        cls.username3 = 'ews_user3'
        cls.password3 = 'dummy'
        cls.web_user3 = WebUser.create(TEST_DOMAIN, cls.username3, cls.password3)
        cls.web_user3.get_domain_membership(TEST_DOMAIN).location_id = cls.testregion2.location_id

        cls.web_user3.eula.signed = True
        cls.web_user3.save()

        cls.username4 = 'ews_user4'
        cls.password4 = 'dummy'
        cls.web_user4 = WebUser.create(TEST_DOMAIN, cls.username4, cls.password4)
        cls.web_user4.get_domain_membership(TEST_DOMAIN).location_id = cls.rsp.location_id

        cls.web_user4.eula.signed = True
        cls.web_user4.save()

        cls.username5 = 'ews_user5'
        cls.password5 = 'dummy'
        cls.web_user5 = WebUser.create(TEST_DOMAIN, cls.username5, cls.password5, first_name='test',
                                       last_name='test2')
        cls.web_user5.set_default_phone_number('1111')
        cls.web_user5.save()
        domain_membership = cls.web_user5.get_domain_membership(TEST_DOMAIN)
        domain_membership.location_id = cls.test_district.location_id
        domain_membership.role_id = UserRole.get_read_only_role_by_domain(cls.domain.name).get_id

        cls.web_user5.eula.signed = True
        cls.web_user5.save()

        cls.username6 = 'ews_user6'
        cls.password6 = 'dummy'
        cls.web_user6 = WebUser.create(TEST_DOMAIN, cls.username6, cls.password6)
        domain_membership = cls.web_user6.get_domain_membership(TEST_DOMAIN)
        domain_membership.role_id = UserRole.get_read_only_role_by_domain(cls.domain.name).get_id

        cls.web_user6.eula.signed = True
        cls.web_user6.save()

        cls.admin_username = 'admin'
        cls.admin_password = 'dummy'
        cls.admin = WebUser.create(TEST_DOMAIN, cls.admin_username, cls.admin_password)
        domain_membership = cls.admin.get_domain_membership(TEST_DOMAIN)
        domain_membership.role_id = UserRole.by_domain_and_name(cls.domain.name, 'Administrator')[0].get_id

        cls.admin.eula.signed = True
        cls.admin.save()

        EWSExtension.objects.create(
            user_id=cls.web_user6.get_id,
            domain=TEST_DOMAIN,
            location_id=cls.test_facility3.get_id
        )

        cls.ad = SQLProduct.objects.get(domain=TEST_DOMAIN, code='ad')
        cls.al = SQLProduct.objects.get(domain=TEST_DOMAIN, code='al')

        cls.backend, cls.mapping = setup_default_sms_test_backend()
        cls.client = Client()

    def setUp(self):
        super(TestInputStockView, self).setUp()
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    def test_access_for_non_existing_location(self):
        self.client.login(username=self.username5, password=self.password5)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'invalidcode'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 404)

    def test_web_user_without_location(self):
        self.client.login(username=self.username1, password=self.password1)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'rsp'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 403)

    def test_web_user_with_wrong_location_access(self):
        """
            User assigned to reporting location can send data only for this particular facility.
        """
        self.client.login(username=self.username4, password=self.password4)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 403)

    def test_web_user_with_not_parent_location_access(self):
        """
            User assigned to non-reporting location can send data only for facilities below his location level
        """
        self.client.login(username=self.username3, password=self.password3)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 403)

    def test_web_user_with_valid_location_access(self):
        self.client.login(username=self.username2, password=self.password2)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 200)
        formset = response.context['formset']
        tsactive = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='tsactive')
        self.assertIsNotNone(formset)
        self.assertEqual(tsactive.products.count(), 2)
        self.assertEqual(len(list(formset)), tsactive.products.count())

    def test_web_user_with_extension(self):
        self.client.login(username=self.username6, password=self.password6)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_web_user_with_valid_parent_location_access(self):
        self.client.login(username=self.username5, password=self.password5)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 200)
        formset = response.context['formset']
        tsactive = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='tsactive')
        self.assertIsNotNone(formset)
        self.assertEqual(tsactive.products.count(), 2)
        self.assertEqual(len(list(formset)), tsactive.products.count())

    def test_admin_web_user_access(self):
        self.client.login(username=self.admin_username, password=self.admin_password)

        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 200)

        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'rsp'})
        response = self.client.get(view_url, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_web_user_report_submission(self):
        self.client.login(username=self.username5, password=self.password5)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': 1000
        }
        tsactive = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='tsactive')

        data['form-0-product_id'] = self.ad.product_id
        data['form-0-product'] = 'ad'
        data['form-0-stock_on_hand'] = 20
        data['form-0-receipts'] = 30

        data['form-1-product_id'] = self.al.product_id
        data['form-1-product'] = 'al'
        data['form-1-stock_on_hand'] = 14
        data['form-1-receipts'] = 17

        response = self.client.post(view_url, data=data)
        url = make_url(
            StockStatus,
            self.domain,
            '?location_id=%s&filter_by_program=all&startdate='
            '&enddate=&report_type=&filter_by_product=all',
            (tsactive.location_id, )
        )
        self.assertRedirects(response, url)
        messages = SMS.objects.filter(domain=TEST_DOMAIN)
        self.assertEqual(messages.count(), 1)
        self.assertEqual(
            messages[0].text,
            'Dear test test2, thank you for reporting the commodities you have. You received ad 30 al 17.'
        )

        stock_states = StockState.objects.filter(case_id=tsactive.supply_point_id)
        stock_transactions = StockTransaction.objects.filter(case_id=tsactive.supply_point_id)

        self.assertEqual(stock_states.count(), 2)
        self.assertEqual(stock_transactions.count(), 6)
        self.assertEqual(stock_transactions.filter(type='consumption').count(), 2)
        self.assertEqual(stock_transactions.filter(type='stockonhand').count(), 2)
        self.assertEqual(stock_transactions.filter(type='receipts').count(), 2)

        ad_consumption = stock_transactions.filter(type='consumption', product_id=self.ad.product_id)[0].quantity
        al_consumption = stock_transactions.filter(type='consumption', product_id=self.al.product_id)[0].quantity

        self.assertEqual(ad_consumption, Decimal(-10))
        self.assertEqual(al_consumption, Decimal(-3))

        al_stock_state = StockState.objects.get(case_id=tsactive.supply_point_id, product_id=self.al.product_id)
        ad_stock_state = StockState.objects.get(case_id=tsactive.supply_point_id, product_id=self.ad.product_id)

        self.assertEqual(int(ad_stock_state.stock_on_hand), 20)
        self.assertEqual(int(al_stock_state.stock_on_hand), 14)

        reports = StockReport.objects.filter(domain=TEST_DOMAIN)

        self.assertEqual(reports.count(), 2)

    def test_incomplete_report_submission(self):
        self.client.login(username=self.username5, password=self.password5)
        view_url = reverse('input_stock', kwargs={'domain': TEST_DOMAIN, 'site_code': 'tsactive'})
        data = {
            'form-TOTAL_FORMS': 2,
            'form-INITIAL_FORMS': 2,
            'form-MAX_NUM_FORMS': 1000
        }
        tsactive = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='tsactive')

        data['form-0-product_id'] = self.ad.product_id
        data['form-0-product'] = 'ad'
        data['form-0-stock_on_hand'] = ''
        data['form-0-receipts'] = ''

        data['form-1-product_id'] = self.al.product_id
        data['form-1-product'] = 'al'
        data['form-1-stock_on_hand'] = 14
        data['form-1-receipts'] = 17

        response = self.client.post(view_url, data=data)
        url = make_url(
            StockStatus,
            self.domain,
            '?location_id=%s&filter_by_program=all&startdate='
            '&enddate=&report_type=&filter_by_product=all',
            (tsactive.location_id, )
        )
        self.assertRedirects(response, url)

        stock_states = StockState.objects.filter(case_id=tsactive.supply_point_id)
        stock_transactions = StockTransaction.objects.filter(case_id=tsactive.supply_point_id)

        self.assertEqual(stock_states.count(), 1)
        self.assertEqual(stock_transactions.count(), 3)

        ad_transactions = stock_transactions.filter(product_id=self.ad.product_id)
        self.assertEqual(ad_transactions.count(), 0)

        with self.assertRaises(StockState.DoesNotExist):
            StockState.objects.get(case_id=tsactive.supply_point_id,
                                   product_id=self.ad.product_id)

    @classmethod
    def tearDownClass(cls):
        cls.mapping.delete()
        cls.backend.delete()
        cls.web_user1.delete()
        cls.domain.delete()
        cls.teardown_subscription()
        clear_plan_version_cache()
        super(TestInputStockView, cls).tearDownClass()
