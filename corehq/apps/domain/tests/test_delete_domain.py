import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from dateutil.relativedelta import relativedelta
from mock import patch

from casexml.apps.case.mock import CaseFactory
from casexml.apps.phone.models import OwnershipCleanlinessFlag, SyncLogSQL
from couchforms.models import UnfinishedSubmissionStub

from corehq.apps.accounting.models import (
    BillingAccount,
    CreditLine,
    DefaultProductPlan,
    FeatureType,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.aggregate_ucrs.models import (
    AggregateTableDefinition,
    PrimaryColumn,
    SecondaryColumn,
    SecondaryTableDefinition,
)
from corehq.apps.app_manager.models import (
    AppReleaseByLocation,
    GlobalAppConfig,
    LatestEnabledBuildProfiles,
)
from corehq.apps.app_manager.suite_xml.post_process.resources import (
    ResourceOverride,
)
from corehq.apps.case_importer.tracking.models import (
    CaseUploadFormRecord,
    CaseUploadRecord,
)
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
)
from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.consumption.models import DefaultConsumption
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.data_analytics.models import GIRRow, MALTRow
from corehq.apps.data_dictionary.models import CaseProperty, CasePropertyAllowedValue, CaseType
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseRuleAction,
    CaseRuleCriteria,
    CaseRuleSubmission,
    DomainCaseRuleRun,
)
from corehq.apps.domain.models import Domain, TransferDomainRequest
from corehq.apps.export.models.new import DataFile, EmailExportWhenDoneRequest
from corehq.apps.ivr.models import Call
from corehq.apps.locations.models import (
    LocationFixtureConfiguration,
    LocationType,
    SQLLocation,
    make_location,
)
from corehq.apps.ota.models import MobileRecoveryMeasure, SerialIdBucket
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.reminders.models import EmailUsage
from corehq.apps.reports.models import (
    ReportsSidebarOrdering,
    TableauServer,
    TableauVisualization,
)
from corehq.apps.sms.models import (
    SMS,
    DailyOutboundSMSLimitReached,
    ExpectedCallback,
    Keyword,
    KeywordAction,
    MessagingEvent,
    MessagingSubEvent,
    MobileBackendInvitation,
    PhoneNumber,
    QueuedSMS,
    SQLLastReadMessage,
    SQLMobileBackend,
    SQLMobileBackendMapping,
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.translations.models import SMSTranslations, TransifexBlacklist
from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import (
    DomainRequest,
    Invitation,
    PermissionInfo,
    Permissions,
    RoleAssignableBy,
    RolePermission,
    UserRole,
    UserHistory,
    WebUser,
)
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.apps.zapier.consts import EventTypes
from corehq.apps.zapier.models import ZapierSubscription
from corehq.blobs import CODES, NotFound, get_blob_db
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    doc_type_to_state,
)
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.tests.utils import create_form_for_test
from corehq.motech.models import ConnectionSettings, RequestLog
from corehq.motech.repeaters.const import RECORD_SUCCESS_STATE
from corehq.motech.repeaters.models import (
    SQLRepeater,
    SQLRepeatRecord,
    SQLRepeatRecordAttempt,
)
from settings import HQ_ACCOUNT_ROOT


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
        backend = SQLMobileBackend.objects.create(domain=domain_name, is_global=False)
        SQLMobileBackendMapping.objects.create(
            domain=domain_name,
            backend_type=SQLMobileBackend.SMS,
            prefix=str(i),
            backend=backend
        )
        MobileBackendInvitation.objects.create(domain=domain_name, backend=backend)

    def setUp(self):
        super(TestDeleteDomain, self).setUp()
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.addCleanup(ensure_deleted, self.domain)
        self.domain.convert_to_commtrack()
        self.current_subscription = Subscription.new_domain_subscription(
            BillingAccount.get_or_create_account_by_domain(self.domain.name, created_by='tests')[0],
            self.domain.name,
            DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ADVANCED),
            date_start=date.today() - relativedelta(days=1),
        )

        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()
        self.addCleanup(self.domain2.delete)
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
        self.assertEqual(SQLLocation.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLProduct.objects.filter(domain=domain).count(), number)
        self.assertEqual(LocationType.objects.filter(domain=domain).count(), number)

        self.assertEqual(SMS.objects.filter(domain=domain).count(), number)
        self.assertEqual(Call.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLLastReadMessage.objects.filter(domain=domain).count(), number)
        self.assertEqual(ExpectedCallback.objects.filter(domain=domain).count(), number)
        self.assertEqual(PhoneNumber.objects.filter(domain=domain).count(), number)
        self.assertEqual(MessagingEvent.objects.filter(domain=domain).count(), number)
        self.assertEqual(MessagingSubEvent.objects.filter(parent__domain=domain).count(), number)
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

        # Check that get_credits_by_subscription_and_features does not return the old deactivated credit line
        subscription_credits = CreditLine.get_credits_by_subscription_and_features(
            self.current_subscription,
            feature_type=FeatureType.SMS,
        )
        self.assertEqual(len(subscription_credits), 0)

        # Check that old credit line has been tranferred to accoun
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

    def test_case_deletion_sql(self):
        self._test_case_deletion()

    def test_form_deletion(self):
        form_states = [state_tuple[0] for state_tuple in XFormInstanceSQL.STATES]

        for domain_name in [self.domain.name, self.domain2.name]:
            for form_state in form_states:
                create_form_for_test(domain_name, state=form_state)
            for doc_type in doc_type_to_state:
                self.assertEqual(
                    len(FormAccessors(domain_name).get_all_form_ids_in_domain(doc_type=doc_type)),
                    1
                )

        self.domain.delete()

        for doc_type in doc_type_to_state:
            self.assertEqual(
                len(FormAccessors(self.domain.name).get_all_form_ids_in_domain(doc_type=doc_type)),
                0
            )
            self.assertEqual(
                len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain(doc_type=doc_type)),
                1
            )

    def _assert_queryset_count(self, queryset_list, count):
        for queryset in queryset_list:
            self.assertEqual(queryset.count(), count)

    def _assert_aggregate_ucr_count(self, domain_name, count):
        self._assert_queryset_count([
            AggregateTableDefinition.objects.filter(domain=domain_name),
            PrimaryColumn.objects.filter(table_definition__domain=domain_name),
            SecondaryTableDefinition.objects.filter(table_definition__domain=domain_name),
            SecondaryColumn.objects.filter(table_definition__table_definition__domain=domain_name),
        ], count)

    def test_aggregate_ucr_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            aggregate_table_definition = AggregateTableDefinition.objects.create(
                domain=domain_name,
                primary_data_source_id=uuid.uuid4(),
                table_id=uuid.uuid4().hex,
            )
            secondary_table_definition = SecondaryTableDefinition.objects.create(
                table_definition=aggregate_table_definition,
                data_source_id=uuid.uuid4(),
            )
            PrimaryColumn.objects.create(table_definition=aggregate_table_definition)
            SecondaryColumn.objects.create(table_definition=secondary_table_definition)
            self._assert_aggregate_ucr_count(domain_name, 1)

        self.domain.delete()

        self._assert_aggregate_ucr_count(self.domain.name, 0)
        self._assert_aggregate_ucr_count(self.domain2.name, 1)

        self.assertEqual(SecondaryTableDefinition.objects.count(), 1)
        self.assertEqual(
            SecondaryTableDefinition.objects.filter(table_definition__domain=self.domain2.name).count(),
            1
        )
        self.assertEqual(PrimaryColumn.objects.count(), 1)
        self.assertEqual(PrimaryColumn.objects.filter(table_definition__domain=self.domain2.name).count(), 1)
        self.assertEqual(SecondaryColumn.objects.count(), 1)
        self.assertEqual(
            SecondaryColumn.objects.filter(table_definition__table_definition__domain=self.domain2.name).count(),
            1
        )

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
                form_id=uuid.uuid4().hex,
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

    def _assert_app_manager_counts(self, domain_name, count):
        self._assert_queryset_count([
            AppReleaseByLocation.objects.filter(domain=domain_name),
            LatestEnabledBuildProfiles.objects.filter(domain=domain_name),
            GlobalAppConfig.objects.filter(domain=domain_name),
            ResourceOverride.objects.filter(domain=domain_name),
        ], count)

    def test_app_manager(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            location = make_location(
                domain=domain_name,
                site_code='testcode',
                name='test',
                location_type='facility'
            )
            location.save()
            AppReleaseByLocation.objects.create(domain=domain_name, app_id='123', build_id='456',
                                                version=23, location=location)
            with patch('corehq.apps.app_manager.models.GlobalAppConfig.by_app_id'):
                LatestEnabledBuildProfiles.objects.create(domain=domain_name, app_id='123', build_id='456',
                                                          version=10)
            GlobalAppConfig.objects.create(domain=domain_name, app_id='123')
            ResourceOverride.objects.create(domain=domain_name, app_id='123', root_name='test',
                                            pre_id='456', post_id='789')
            self._assert_app_manager_counts(domain_name, 1)

        self.domain.delete()

        self._assert_app_manager_counts(self.domain.name, 0)
        self._assert_app_manager_counts(self.domain2.name, 1)

        location.delete()

    def _assert_case_search_counts(self, domain_name, count):
        self._assert_queryset_count([
            CaseSearchConfig.objects.filter(domain=domain_name),
            FuzzyProperties.objects.filter(domain=domain_name),
            IgnorePatterns.objects.filter(domain=domain_name),
        ], count)

    def test_case_search(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CaseSearchConfig.objects.create(domain=domain_name)
            FuzzyProperties.objects.create(domain=domain_name)
            IgnorePatterns.objects.create(domain=domain_name)
            self._assert_case_search_counts(domain_name, 1)

        self.domain.delete()

        self._assert_case_search_counts(self.domain.name, 0)
        self._assert_case_search_counts(self.domain2.name, 1)

    def _assert_cloudcare_counts(self, domain_name, count):
        self._assert_queryset_count([
            ApplicationAccess.objects.filter(domain=domain_name),
        ], count)

    def test_cloudcare(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            get_application_access_for_domain(domain_name)

        self.domain.delete()

        self._assert_cloudcare_counts(self.domain.name, 0)
        self._assert_cloudcare_counts(self.domain2.name, 1)

    def _assert_consumption_counts(self, domain_name, count):
        self._assert_queryset_count([
            DefaultConsumption.objects.filter(domain=domain_name),
        ], count)

    def test_consumption(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            DefaultConsumption.objects.create(domain=domain_name)

        self.domain.delete()

        self._assert_consumption_counts(self.domain.name, 0)
        self._assert_consumption_counts(self.domain2.name, 1)

    def _assert_custom_data_fields_counts(self, domain_name, count):
        self._assert_queryset_count([
            CustomDataFieldsDefinition.objects.filter(domain=domain_name),
        ], count)

    def test_custom_data_fields(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CustomDataFieldsDefinition.get_or_create(domain_name, 'UserFields')

        self.domain.delete()

        self._assert_custom_data_fields_counts(self.domain.name, 0)
        self._assert_custom_data_fields_counts(self.domain2.name, 1)

    def _assert_data_analytics_counts(self, domain_name, count):
        self._assert_queryset_count([
            GIRRow.objects.filter(domain_name=domain_name),
            MALTRow.objects.filter(domain_name=domain_name),
        ], count)

    def test_data_analytics(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            GIRRow.objects.create(
                domain_name=domain_name,
                month=date.today(),
                start_date=date.today(),
                wams_current=1,
                active_users=1,
                using_and_performing=1,
                not_performing=1,
                inactive_experienced=1,
                inactive_not_experienced=1,
                not_experienced=1,
                not_performing_not_experienced=1,
                active_ever=1,
                possibly_exp=1,
                ever_exp=1,
                exp_and_active_ever=1,
                active_in_span=1,
                eligible_forms=1,
            )
            MALTRow.objects.create(
                domain_name=domain_name,
                month=date.today(),
                num_of_forms=1,
            )
            self._assert_data_analytics_counts(domain_name, 1)

        self.domain.delete()

        self._assert_data_analytics_counts(self.domain.name, 0)
        self._assert_data_analytics_counts(self.domain2.name, 1)

    def _assert_data_dictionary_counts(self, domain_name, count):
        self._assert_queryset_count([
            CaseType.objects.filter(domain=domain_name),
            CaseProperty.objects.filter(case_type__domain=domain_name),
            CasePropertyAllowedValue.objects.filter(case_property__case_type__domain=domain_name),
        ], count)

    def test_data_dictionary(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            case_type = CaseType.objects.create(domain=domain_name, name='case_type')
            prop = CaseProperty.objects.create(case_type=case_type, name='case_property', data_type='select')
            CasePropertyAllowedValue.objects.create(case_property=prop, allowed_value="True")
            self._assert_data_dictionary_counts(domain_name, 1)

        self.domain.delete()

        self._assert_data_dictionary_counts(self.domain.name, 0)
        self._assert_data_dictionary_counts(self.domain2.name, 1)

    def _assert_data_interfaces(self, domain_name, count):
        self._assert_queryset_count([
            AutomaticUpdateRule.objects.filter(domain=domain_name),
            CaseRuleAction.objects.filter(rule__domain=domain_name),
            CaseRuleCriteria.objects.filter(rule__domain=domain_name),
            CaseRuleSubmission.objects.filter(domain=domain_name),
            DomainCaseRuleRun.objects.filter(domain=domain_name),
        ], count)

    def test_data_interfaces(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            automatic_update_rule = AutomaticUpdateRule.objects.create(domain=domain_name)
            CaseRuleAction.objects.create(rule=automatic_update_rule)
            CaseRuleCriteria.objects.create(rule=automatic_update_rule)
            CaseRuleSubmission.objects.create(
                created_on=datetime.utcnow(),
                domain=domain_name,
                form_id=uuid.uuid4().hex,
                rule=automatic_update_rule,
            )
            DomainCaseRuleRun.objects.create(domain=domain_name, started_on=datetime.utcnow())
            self._assert_data_interfaces(domain_name, 1)

        self.domain.delete()

        self._assert_data_interfaces(self.domain.name, 0)
        self._assert_data_interfaces(self.domain2.name, 1)

        self.assertEqual(CaseRuleAction.objects.count(), 1)
        self.assertEqual(CaseRuleAction.objects.filter(rule__domain=self.domain2.name).count(), 1)
        self.assertEqual(CaseRuleCriteria.objects.count(), 1)
        self.assertEqual(CaseRuleCriteria.objects.filter(rule__domain=self.domain2.name).count(), 1)

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

    def _assert_export_counts(self, domain_name, count):
        self._assert_queryset_count([
            DataFile.meta_query(domain_name),
            EmailExportWhenDoneRequest.objects.filter(domain=domain_name),
        ], count)

    def test_export_delete(self):
        blobdb = get_blob_db()
        data_files = []
        for domain_name in [self.domain.name, self.domain2.name]:
            data_files.append(DataFile.save_blob(
                BytesIO((domain_name + " csv").encode('utf-8')),
                domain=domain_name,
                filename="data.csv",
                description="data file",
                content_type="text/csv",
                delete_after=datetime.utcnow() + timedelta(minutes=10),
            ))
            EmailExportWhenDoneRequest.objects.create(domain=domain_name)
            self._assert_export_counts(domain_name, 1)

        self.domain.delete()

        with self.assertRaises(NotFound):
            blobdb.get(key=data_files[0].blob_id, type_code=CODES.data_file)

        with blobdb.get(key=data_files[1].blob_id, type_code=CODES.data_file) as f:
            self.assertEqual(f.read(), (self.domain2.name + " csv").encode('utf-8'))

        self._assert_export_counts(self.domain.name, 0)
        self._assert_export_counts(self.domain2.name, 1)

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

    def _assert_ota_counts(self, domain_name, count):
        self._assert_queryset_count([
            MobileRecoveryMeasure.objects.filter(domain=domain_name),
            SerialIdBucket.objects.filter(domain=domain_name),
        ], count)

    def test_ota_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            MobileRecoveryMeasure.objects.create(domain=domain_name)
            SerialIdBucket.objects.create(domain=domain_name)
            self._assert_ota_counts(domain_name, 1)

        self.domain.delete()

        self._assert_ota_counts(self.domain.name, 0)
        self._assert_ota_counts(self.domain2.name, 1)

    def _assert_reports_counts(self, domain_name, count):
        self._assert_queryset_count([
            ReportsSidebarOrdering.objects.filter(domain=domain_name),
            TableauServer.objects.filter(domain=domain_name),
            TableauVisualization.objects.filter(domain=domain_name),
        ], count)

    def test_reports_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            ReportsSidebarOrdering.objects.create(domain=domain_name)
            server = TableauServer.objects.create(
                domain=domain_name,
                server_type='server',
                server_name='my_server',
                target_site='my_site',
                domain_username='my_username',
            )
            TableauVisualization.objects.create(
                domain=domain_name,
                server=server,
                view_url='my_url',
            )
            self._assert_reports_counts(domain_name, 1)

        self.domain.delete()

        self._assert_reports_counts(self.domain.name, 0)
        self._assert_reports_counts(self.domain2.name, 1)

    def _assert_phone_counts(self, domain_name, count):
        self._assert_queryset_count([
            OwnershipCleanlinessFlag.objects.filter(domain=domain_name),
            SyncLogSQL.objects.filter(domain=domain_name)
        ], count)

    def test_phone_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            OwnershipCleanlinessFlag.objects.create(domain=domain_name)
            SyncLogSQL.objects.create(
                domain=domain_name,
                doc={},
                synclog_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )
            self._assert_phone_counts(domain_name, 1)

        self.domain.delete()

        self._assert_phone_counts(self.domain.name, 0)
        self._assert_phone_counts(self.domain2.name, 1)

    def _assert_registration_count(self, domain_name, count):
        self._assert_queryset_count([
            RegistrationRequest.objects.filter(domain=domain_name),
        ], count)

    def test_registration_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            RegistrationRequest.objects.create(
                domain=domain_name,
                activation_guid=uuid.uuid4().hex,
                request_time=datetime.utcnow(),
                request_ip='12.34.567.8'
            )
            self._assert_registration_count(domain_name, 1)

        self.domain.delete()

        self._assert_registration_count(self.domain.name, 0)
        self._assert_registration_count(self.domain2.name, 1)

    def _assert_reminders_counts(self, domain_name, count):
        self._assert_queryset_count([
            EmailUsage.objects.filter(domain=domain_name),
        ], count)

    def test_reminders_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            EmailUsage.objects.create(domain=domain_name, month=7, year=2018)
            self._assert_reminders_counts(domain_name, 1)

        self.domain.delete()

        self._assert_reminders_counts(self.domain.name, 0)
        self._assert_reminders_counts(self.domain2.name, 1)

    def _assert_sms_counts(self, domain_name, count):
        self._assert_queryset_count([
            DailyOutboundSMSLimitReached.objects.filter(domain=domain_name),
            Keyword.objects.filter(domain=domain_name),
            KeywordAction.objects.filter(keyword__domain=domain_name),
            QueuedSMS.objects.filter(domain=domain_name)
        ], count)

    def test_sms_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            DailyOutboundSMSLimitReached.objects.create(domain=domain_name, date=date.today())
            keyword = Keyword.objects.create(domain=domain_name)
            KeywordAction.objects.create(keyword=keyword)
            QueuedSMS.objects.create(domain=domain_name)
            self._assert_sms_counts(domain_name, 1)

        self.domain.delete()

        self._assert_sms_counts(self.domain.name, 0)
        self._assert_sms_counts(self.domain2.name, 1)

        self.assertEqual(KeywordAction.objects.count(), 1)
        self.assertEqual(KeywordAction.objects.filter(keyword__domain=self.domain2.name).count(), 1)

    def _assert_smsforms_counts(self, domain_name, count):
        self._assert_queryset_count([
            SQLXFormsSession.objects.filter(domain=domain_name),
        ], count)

    def test_smsforms_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            SQLXFormsSession.objects.create(
                domain=domain_name,
                start_time=datetime.utcnow(),
                modified_time=datetime.utcnow(),
                current_action_due=datetime.utcnow(),
                expire_after=3,
            )
            self._assert_smsforms_counts(domain_name, 1)

        self.domain.delete()

        self._assert_smsforms_counts(self.domain.name, 0)
        self._assert_smsforms_counts(self.domain2.name, 1)

    def _assert_translations_count(self, domain_name, count):
        self._assert_queryset_count([
            SMSTranslations.objects.filter(domain=domain_name),
            TransifexBlacklist.objects.filter(domain=domain_name),
        ], count)

    def test_translations_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            SMSTranslations.objects.create(domain=domain_name, langs=['en'], translations={'a': 'a'})
            TransifexBlacklist.objects.create(domain=domain_name, app_id='123', field_name='xyz')
            self._assert_translations_count(domain_name, 1)

        self.domain.delete()

        self._assert_translations_count(self.domain.name, 0)
        self._assert_translations_count(self.domain2.name, 1)

    def _assert_userreports_counts(self, domain_name, count):
        self._assert_queryset_count([
            AsyncIndicator.objects.filter(domain=domain_name)
        ], count)

    def test_userreports_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            AsyncIndicator.objects.create(
                domain=domain_name,
                doc_id=uuid.uuid4().hex,
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
            Invitation.objects.filter(domain=domain_name),
            User.objects.filter(username__contains=f'{domain_name}.{HQ_ACCOUNT_ROOT}')
        ], count)

    def test_users_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            DomainRequest.objects.create(domain=domain_name, email='user@test.com', full_name='User')
            Invitation.objects.create(domain=domain_name, email='user@test.com',
                                      invited_by='friend@test.com', invited_on=datetime.utcnow())
            User.objects.create(username=f'mobileuser@{domain_name}.{HQ_ACCOUNT_ROOT}')
            self._assert_users_counts(domain_name, 1)

        self.domain.delete()

        self._assert_users_counts(self.domain.name, 0)
        self._assert_users_counts(self.domain2.name, 1)

    def test_users_domain_membership(self):
        web_user = WebUser.create(self.domain.name, f'webuser@{self.domain.name}.{HQ_ACCOUNT_ROOT}', '******',
                                  created_by=None, created_via=None)

        another_domain = Domain(name="another-test", is_active=True)
        another_domain.save()
        self.addCleanup(another_domain.delete)

        # add more than 1 domain membership to trigger _log_web_user_membership_removed in tests
        web_user.add_domain_membership(another_domain.name)
        web_user.save()

        self.domain.delete()

        user_history = UserHistory.objects.last()
        self.assertEqual(user_history.by_domain, None)
        self.assertEqual(user_history.for_domain, self.domain.name)
        self.assertEqual(user_history.changed_by, SYSTEM_USER_ID)
        self.assertEqual(user_history.user_id, web_user.get_id)
        self.assertEqual(user_history.change_messages, UserChangeMessage.domain_removal(self.domain.name))
        self.assertEqual(user_history.changed_via,
                         'corehq.apps.domain.deletion._delete_web_user_membership')
        self.assertEqual(user_history.changes, {})

    def _assert_role_counts(self, domain_name, roles, permissions, assignments):
        self.assertEqual(UserRole.objects.filter(domain=domain_name).count(), roles)
        self.assertEqual(RolePermission.objects.filter(role__domain=domain_name).count(), permissions)
        self.assertEqual(RoleAssignableBy.objects.filter(role__domain=domain_name).count(), assignments)

    def test_roles_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            role1 = UserRole.objects.create(
                domain=domain_name,
                name="role1"
            )
            role = UserRole.objects.create(
                domain=domain_name,
                name="role2"
            )
            role.set_permissions([
                PermissionInfo(Permissions.view_reports.name, allow=PermissionInfo.ALLOW_ALL)
            ])
            role.set_assignable_by([role1.id])
            self._assert_role_counts(domain_name, 2, 1, 1)

        self.domain.delete()

        self._assert_role_counts(self.domain.name, 0, 0, 0)
        self._assert_role_counts(self.domain2.name, 2, 1, 1)

    def _assert_zapier_counts(self, domain_name, count):
        self._assert_queryset_count([
            ZapierSubscription.objects.filter(domain=domain_name),
        ], count)

    def test_zapier_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            ZapierSubscription.objects.create(
                domain=domain_name,
                case_type='case_type',
                event_name=EventTypes.NEW_CASE,
                url='http://%s.com' % domain_name,
                user_id='user_id',
            )
            self._assert_zapier_counts(domain_name, 1)

        self.domain.delete()

        self._assert_zapier_counts(self.domain.name, 0)
        self._assert_zapier_counts(self.domain2.name, 1)

    def _assert_motech_count(self, domain_name, count):
        self._assert_queryset_count([
            RequestLog.objects.filter(domain=domain_name),
        ], count)

    def test_motech_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            RequestLog.objects.create(domain=domain_name)
            self._assert_motech_count(domain_name, 1)

        self.domain.delete()

        self._assert_motech_count(self.domain.name, 0)
        self._assert_motech_count(self.domain2.name, 1)

    def _assert_repeaters_count(self, domain_name, count):
        self._assert_queryset_count([
            SQLRepeater.objects.filter(domain=domain_name),
            SQLRepeatRecord.objects.filter(domain=domain_name),
            SQLRepeatRecordAttempt.objects.filter(repeat_record__domain=domain_name),
        ], count)

    def test_repeaters_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            conn = ConnectionSettings.objects.create(
                domain=domain_name,
                name='To Be Deleted',
                url="http://localhost/api/"
            )
            repeater = SQLRepeater.objects.create(
                domain=domain_name,
                repeater_id=str(uuid.uuid4()),
                connection_settings=conn
            )
            record = repeater.repeat_records.create(
                domain=domain_name,
                payload_id=str(uuid.uuid4()),
                registered_at=datetime.utcnow(),
            )
            record.sqlrepeatrecordattempt_set.create(
                state=RECORD_SUCCESS_STATE,
            )
            self._assert_repeaters_count(domain_name, 1)

        self.domain.delete()

        self._assert_repeaters_count(self.domain.name, 0)
        self._assert_repeaters_count(self.domain2.name, 1)

    def _assert_couchforms_counts(self, domain_name, count):
        self._assert_queryset_count([
            UnfinishedSubmissionStub.objects.filter(domain=domain_name)
        ], count)

    def test_couchforms_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            UnfinishedSubmissionStub.objects.create(
                domain=domain_name,
                timestamp=datetime.utcnow(),
                xform_id='xform_id',
            )
            self._assert_couchforms_counts(domain_name, 1)

        self.domain.delete()

        self._assert_couchforms_counts(self.domain.name, 0)
        self._assert_couchforms_counts(self.domain2.name, 1)

    def test_delete_commtrack_config(self):
        # Config will have been created by convert_to_commtrack in setUp
        self.assertIsNotNone(CommtrackConfig.for_domain(self.domain.name))
        self.domain.delete()
        self.assertIsNone(CommtrackConfig.for_domain(self.domain.name))


class TestHardDeleteSQLFormsAndCases(TestCase):

    def setUp(self):
        super(TestHardDeleteSQLFormsAndCases, self).setUp()
        self.domain = Domain(name='test')
        self.domain.save()
        self.addCleanup(ensure_deleted, self.domain)
        self.domain2 = Domain(name='test2')
        self.domain2.save()
        self.addCleanup(self.domain2.delete)

    def tearDown(self):
        call_command('hard_delete_forms_and_cases_in_domain', self.domain2.name, noinput=True)
        call_command('hard_delete_forms_and_cases_in_domain', self.domain.name, noinput=True)
        super(TestHardDeleteSQLFormsAndCases, self).tearDown()

    def test_hard_delete_forms(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            create_form_for_test(domain_name)
            create_form_for_test(domain_name, state=XFormInstanceSQL.ARCHIVED)
            self.assertEqual(len(FormAccessors(domain_name).get_all_form_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(FormAccessors(self.domain.name).get_all_form_ids_in_domain()), 0)
        self.assertEqual(len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain()), 1)

        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain.name)), 2)
        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain2.name)), 0)

        call_command('hard_delete_forms_and_cases_in_domain', self.domain.name, noinput=True)

        self.assertEqual(len(FormAccessors(self.domain.name).get_all_form_ids_in_domain()), 0)
        self.assertEqual(len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain()), 1)

        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain.name)), 0)
        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain2.name)), 0)

    def test_hard_delete_forms_none_to_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            create_form_for_test(domain_name)
            create_form_for_test(domain_name, state=XFormInstanceSQL.ARCHIVED)
            self.assertEqual(len(FormAccessors(domain_name).get_all_form_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(FormAccessors(self.domain.name).get_all_form_ids_in_domain()), 0)
        self.assertEqual(len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain()), 1)

        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain.name)), 2)
        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain2.name)), 0)

        call_command('hard_delete_forms_and_cases_in_domain', self.domain2.name, noinput=True)

        self.assertEqual(len(FormAccessors(self.domain.name).get_all_form_ids_in_domain()), 0)
        self.assertEqual(len(FormAccessors(self.domain2.name).get_all_form_ids_in_domain()), 1)

        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain.name)), 2)
        self.assertEqual(len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain2.name)), 0)

    def test_hard_delete_cases(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CaseFactory(domain_name).create_case()
            self.assertEqual(len(CaseAccessors(domain_name).get_case_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(CaseAccessors(self.domain.name).get_case_ids_in_domain()), 0)
        self.assertEqual(len(CaseAccessors(self.domain2.name).get_case_ids_in_domain()), 1)

        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain.name)), 1)
        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain2.name)), 0)

        call_command('hard_delete_forms_and_cases_in_domain', self.domain.name, noinput=True)

        self.assertEqual(len(CaseAccessors(self.domain.name).get_case_ids_in_domain()), 0)
        self.assertEqual(len(CaseAccessors(self.domain2.name).get_case_ids_in_domain()), 1)

        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain.name)), 0)
        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain2.name)), 0)

    def test_hard_delete_cases_none_to_delete(self):
        for domain_name in [self.domain.name, self.domain2.name]:
            CaseFactory(domain_name).create_case()
            self.assertEqual(len(CaseAccessors(domain_name).get_case_ids_in_domain()), 1)

        self.domain.delete()

        self.assertEqual(len(CaseAccessors(self.domain.name).get_case_ids_in_domain()), 0)
        self.assertEqual(len(CaseAccessors(self.domain2.name).get_case_ids_in_domain()), 1)

        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain.name)), 1)
        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain2.name)), 0)

        call_command('hard_delete_forms_and_cases_in_domain', self.domain2.name, noinput=True)

        self.assertEqual(len(CaseAccessors(self.domain.name).get_case_ids_in_domain()), 0)
        self.assertEqual(len(CaseAccessors(self.domain2.name).get_case_ids_in_domain()), 1)

        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain.name)), 1)
        self.assertEqual(len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain2.name)), 0)


def ensure_deleted(domain):
    if domain._rev:
        domain.delete()
