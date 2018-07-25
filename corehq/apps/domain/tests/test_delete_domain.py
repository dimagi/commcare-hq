from __future__ import absolute_import
from __future__ import unicode_literals
import random
import uuid
from datetime import date, datetime
from decimal import Decimal
from mock import patch

from dateutil.relativedelta import relativedelta
from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseFactory
from casexml.apps.stock.models import DocDomainMapping, StockReport, StockTransaction

from corehq.apps.accounting.models import (
    BillingAccount,
    CreditLine,
    DefaultProductPlan,
    FeatureType,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.apps.case_importer.tracking.models import CaseUploadFormRecord, CaseUploadRecord
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
    FuzzyProperties,
    IgnorePatterns,
)
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.domain.models import Domain, TransferDomainRequest
from corehq.apps.ivr.models import Call
from corehq.apps.locations.models import make_location, LocationType, SQLLocation, LocationFixtureConfiguration
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.models import ReportsSidebarOrdering
from corehq.apps.sms.models import (SMS, SQLLastReadMessage, ExpectedCallback,
    PhoneNumber, MessagingEvent, MessagingSubEvent, SelfRegistrationInvitation,
    SQLMobileBackend, SQLMobileBackendMapping, MobileBackendInvitation)
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.users.models import DomainRequest
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import create_form_for_test
from dimagi.utils.make_uuid import random_hex
from six.moves import range


class TestDeleteDomain(TestCase):

    def _create_data(self, domain_name, i):
        product = Product(domain=domain_name, name='test-{}'.format(i))
        product.save()

        location = make_location(
            domain=domain_name,
            site_code='testcode-{}'.format(i),
            name='test-{}'.format(i),
            location_type='facility'
        )
        location.save()
        report = StockReport.objects.create(
            type='balance',
            domain=domain_name,
            form_id='fake',
            date=datetime.utcnow(),
            server_date=datetime.utcnow(),
        )

        StockTransaction.objects.create(
            report=report,
            product_id=product.get_id,
            sql_product=SQLProduct.objects.get(product_id=product.get_id),
            section_id='stock',
            type='stockonhand',
            case_id=location.linked_supply_point().get_id,
            stock_on_hand=100
        )

        SMS.objects.create(domain=domain_name)
        Call.objects.create(domain=domain_name)
        SQLLastReadMessage.objects.create(domain=domain_name)
        ExpectedCallback.objects.create(domain=domain_name)
        PhoneNumber.objects.create(domain=domain_name, is_two_way=False, pending_verification=False)
        event = MessagingEvent.objects.create(
            domain=domain_name,
            date=datetime.utcnow(),
            source=MessagingEvent.SOURCE_REMINDER,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED
        )
        MessagingSubEvent.objects.create(
            parent=event,
            date=datetime.utcnow(),
            recipient_type=MessagingEvent.RECIPIENT_CASE,
            content_type=MessagingEvent.CONTENT_SMS,
            status=MessagingEvent.STATUS_COMPLETED
        )
        SelfRegistrationInvitation.objects.create(
            domain=domain_name,
            phone_number='999123',
            token=uuid.uuid4().hex,
            expiration_date=datetime.utcnow().date(),
            created_date=datetime.utcnow()
        )
        backend = SQLMobileBackend.objects.create(domain=domain_name, is_global=False)
        SQLMobileBackendMapping.objects.create(
            domain=domain_name,
            backend_type=SQLMobileBackend.SMS,
            prefix=str(i),
            backend=backend
        )
        MobileBackendInvitation.objects.create(domain=domain_name, backend=backend)

    @classmethod
    def setUpClass(cls):
        super(TestDeleteDomain, cls).setUpClass()

    def setUp(self):
        super(TestDeleteDomain, self).setUp()
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.domain.convert_to_commtrack()
        self.current_subscription = Subscription.new_domain_subscription(
            BillingAccount.get_or_create_account_by_domain(self.domain.name, created_by='tests')[0],
            self.domain.name,
            DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ADVANCED),
            date_start=date.today() - relativedelta(days=1),
        )

        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()
        self.domain2.convert_to_commtrack()

        LocationType.objects.create(
            domain='test',
            name='facility',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility',
        )
        LocationType.objects.create(
            domain='test',
            name='facility2',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility2',
        )

    def _assert_sql_counts(self, domain, number):
        self.assertEqual(StockTransaction.objects.filter(report__domain=domain).count(), number)
        self.assertEqual(StockReport.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLLocation.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLProduct.objects.filter(domain=domain).count(), number)
        self.assertEqual(DocDomainMapping.objects.filter(domain_name=domain).count(), number)
        self.assertEqual(LocationType.objects.filter(domain=domain).count(), number)

        self.assertEqual(SMS.objects.filter(domain=domain).count(), number)
        self.assertEqual(Call.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLLastReadMessage.objects.filter(domain=domain).count(), number)
        self.assertEqual(ExpectedCallback.objects.filter(domain=domain).count(), number)
        self.assertEqual(PhoneNumber.objects.filter(domain=domain).count(), number)
        self.assertEqual(MessagingEvent.objects.filter(domain=domain).count(), number)
        self.assertEqual(MessagingSubEvent.objects.filter(parent__domain=domain).count(), number)
        self.assertEqual(SelfRegistrationInvitation.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLMobileBackend.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLMobileBackendMapping.objects.filter(domain=domain).count(), number)
        self.assertEqual(MobileBackendInvitation.objects.filter(domain=domain).count(), number)

    def test_sql_objects_deletion(self):
        for i in range(2):
            self._create_data('test', i)
            self._create_data('test2', i)

        self._assert_sql_counts('test', 2)
        self._assert_sql_counts('test2', 2)
        self.domain.delete()
        self._assert_sql_counts('test', 0)
        self._assert_sql_counts('test2', 2)

    def test_active_subscription_terminated(self):
        self.domain.delete()

        terminated_subscription = Subscription.visible_objects.get(subscriber__domain=self.domain.name)
        self.assertFalse(terminated_subscription.is_active)
        self.assertIsNotNone(terminated_subscription.date_end)

    def test_accounting_future_subscription_suppressed(self):
        self.current_subscription.date_end = self.current_subscription.date_start + relativedelta(days=5)
        self.current_subscription.save()
        next_subscription = Subscription.new_domain_subscription(
            self.current_subscription.account,
            self.domain.name,
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.PRO),
            date_start=self.current_subscription.date_end,
        )

        self.domain.delete()

        self.assertTrue(
            Subscription.visible_and_suppressed_objects.get(
                id=next_subscription.id
            ).is_hidden_to_ops
        )

    def test_active_subscription_credits_transferred_to_account(self):
        credit_amount = random.randint(1, 10)
        CreditLine.add_credit(
            credit_amount,
            feature_type=FeatureType.SMS,
            subscription=self.current_subscription,
        )

        self.domain.delete()

        subscription_credits = CreditLine.get_credits_by_subscription_and_features(
            self.current_subscription,
            feature_type=FeatureType.SMS,
        )
        self.assertEqual(len(subscription_credits), 1)
        self.assertEqual(subscription_credits[0].balance, Decimal('0.0000'))
        account_credits = CreditLine.get_credits_for_account(
            self.current_subscription.account,
            feature_type=FeatureType.SMS,
        )
        self.assertEqual(len(account_credits), 1)
        self.assertEqual(account_credits[0].balance, Decimal(credit_amount))

    @patch('corehq.apps.accounting.models.DomainDowngradeActionHandler.get_response')
    def test_downgraded(self, mock_get_response):
        mock_get_response.return_value = True

        self.domain.delete()

        self.assertEqual(len(mock_get_response.call_args_list), 1)

    def _test_case_deletion(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CaseFactory(domain_name).create_case()
            self.assertEqual(len(CaseAccessors(domain_name).get_case_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(CaseAccessors(self.domain.name).get_case_ids_in_domain()), 0)
        self.assertEqual(len(CaseAccessors(self.domain2.name).get_case_ids_in_domain()), 1)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_case_deletion_sql(self):
        self._test_case_deletion()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
    def test_case_deletion_couch(self):
        self._test_case_deletion()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_form_deletion(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            create_form_for_test(domain_name)
            self.assertEqual(len(FormAccessors(domain_name).get_all_form_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(FormAccessors(self.domain.name).get_all_form_ids_in_domain()), 0)
        self.assertEqual(len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain()), 1)

    def _assert_queryset_count(self, queryset_list, count):
        for queryset in queryset_list:
            self.assertEqual(queryset.count(), count)

    def _assert_calendar_fixture_count(self, domain_name, count):
        self._assert_queryset_count([
            CalendarFixtureSettings.objects.filter(domain=domain_name)
        ], count)

    def test_calendar_fixture_counts(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CalendarFixtureSettings.objects.create(domain=domain_name, days_before=3, days_after=4)
            self._assert_calendar_fixture_count(domain_name, 1)

        self.domain.delete()

        self._assert_calendar_fixture_count(self.domain.name, 0)
        self._assert_calendar_fixture_count(self.domain2.name, 1)

    def _assert_case_importer_counts(self, domain_name, count):
        self._assert_queryset_count([
            CaseUploadFormRecord.objects.filter(case_upload_record__domain=domain_name),
            CaseUploadRecord.objects.filter(domain=domain_name),
        ], count)

    def test_case_importer(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            case_upload_record = CaseUploadRecord.objects.create(
                domain=domain_name,
                task_id=uuid.uuid4().hex,
                upload_id=uuid.uuid4().hex,
            )
            CaseUploadFormRecord.objects.create(
                case_upload_record=case_upload_record,
                form_id=random_hex(),
            )
            self._assert_case_importer_counts(domain_name, 1)

        self.domain.delete()

        self._assert_case_importer_counts(self.domain.name, 0)
        self._assert_case_importer_counts(self.domain2.name, 1)

        self.assertEqual(CaseUploadFormRecord.objects.count(), 1)
        self.assertEqual(
            CaseUploadFormRecord.objects.filter(case_upload_record__domain=self.domain2.name).count(),
            1
        )

    def _assert_case_search_counts(self, domain_name, count):
        self._assert_queryset_count([
            CaseSearchConfig.objects.filter(domain=domain_name),
            CaseSearchQueryAddition.objects.filter(domain=domain_name),
            FuzzyProperties.objects.filter(domain=domain_name),
            IgnorePatterns.objects.filter(domain=domain_name),
        ], count)

    def test_case_search(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CaseSearchConfig.objects.create(domain=domain_name)
            CaseSearchQueryAddition.objects.create(domain=domain_name)
            FuzzyProperties.objects.create(domain=domain_name)
            IgnorePatterns.objects.create(domain=domain_name)
            self._assert_case_search_counts(domain_name, 1)

        self.domain.delete()

        self._assert_case_search_counts(self.domain.name, 0)
        self._assert_case_search_counts(self.domain2.name, 1)

    def _assert_data_dictionary_counts(self, domain_name, count):
        self._assert_queryset_count([
            CaseType.objects.filter(domain=domain_name),
            CaseProperty.objects.filter(case_type__domain=domain_name),
        ], count)

    def test_data_dictionary(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            case_type = CaseType.objects.create(domain=domain_name, name='case_type')
            CaseProperty.objects.create(case_type=case_type, name='case_property')
            self._assert_data_dictionary_counts(domain_name, 1)

        self.domain.delete()

        self._assert_data_dictionary_counts(self.domain.name, 0)
        self._assert_data_dictionary_counts(self.domain2.name, 1)

    def _assert_domain_counts(self, domain_name, count):
        self._assert_queryset_count([
            TransferDomainRequest.objects.filter(domain=domain_name),
        ], count)

    def test_delete_domain(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            TransferDomainRequest.objects.create(domain=domain_name, to_username='to', from_username='from')
            self._assert_domain_counts(domain_name, 1)

        self.domain.delete()

        self._assert_domain_counts(self.domain.name, 0)
        self._assert_domain_counts(self.domain2.name, 1)

    def _assert_location_counts(self, domain_name, count):
        self._assert_queryset_count([
            LocationFixtureConfiguration.objects.filter(domain=domain_name)
        ], count)

    def test_location_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            LocationFixtureConfiguration.objects.create(domain=domain_name)
            self._assert_location_counts(domain_name, 1)

        self.domain.delete()

        self._assert_location_counts(self.domain.name, 0)
        self._assert_location_counts(self.domain2.name, 1)

    def _assert_reports_counts(self, domain_name, count):
        self._assert_queryset_count([
            ReportsSidebarOrdering.objects.filter(domain=domain_name)
        ], count)

    def test_reports_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            ReportsSidebarOrdering.objects.create(domain=domain_name)
            self._assert_reports_counts(domain_name, 1)

        self.domain.delete()

        self._assert_reports_counts(self.domain.name, 0)
        self._assert_reports_counts(self.domain2.name, 1)

    def _assert_userreports_counts(self, domain_name, count):
        self._assert_queryset_count([
            AsyncIndicator.objects.filter(domain=domain_name)
        ], count)

    def test_userreports_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            AsyncIndicator.objects.create(
                domain=domain_name,
                doc_id=random_hex(),
                doc_type='doc_type',
                indicator_config_ids=[],
            )
            self._assert_userreports_counts(domain_name, 1)

        self.domain.delete()

        self._assert_userreports_counts(self.domain.name, 0)
        self._assert_userreports_counts(self.domain2.name, 1)

    def _assert_users_counts(self, domain_name, count):
        self._assert_queryset_count([
            DomainRequest.objects.filter(domain=domain_name),
        ], count)

    def test_users_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            DomainRequest.objects.create(domain=domain_name, email='user@test.com', full_name='User')
            self._assert_users_counts(domain_name, 1)

        self.domain.delete()

        self._assert_users_counts(self.domain.name, 0)
        self._assert_users_counts(self.domain2.name, 1)

    def tearDown(self):
        self.domain2.delete()
        super(TestDeleteDomain, self).tearDown()
