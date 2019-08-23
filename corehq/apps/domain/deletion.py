from __future__ import absolute_import
from __future__ import unicode_literals

import itertools
import logging
from datetime import date

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import get_change_status
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.domain.utils import silence_during_tests
from corehq.apps.locations.views import LocationFieldsView
from corehq.apps.products.views import ProductFieldsView
from corehq.apps.userreports.dbaccessors import delete_all_ucr_tables_for_domain
from corehq.apps.users.views.mobile import UserFieldsView
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked

logger = logging.getLogger(__name__)


class BaseDeletion(object):

    def __init__(self, app_label):
        self.app_label = app_label

    def is_app_installed(self):
        try:
            return bool(apps.get_app_config(self.app_label))
        except LookupError:
            return False


class CustomDeletion(BaseDeletion):

    def __init__(self, app_label, deletion_fn):
        super(CustomDeletion, self).__init__(app_label)
        self.deletion_fn = deletion_fn

    def execute(self, domain_name):
        if self.is_app_installed():
            self.deletion_fn(domain_name)


class RawDeletion(BaseDeletion):

    def __init__(self, app_label, raw_query):
        super(RawDeletion, self).__init__(app_label)
        self.raw_query = raw_query

    def execute(self, cursor, domain_name):
        if self.is_app_installed():
            cursor.execute(self.raw_query, [domain_name])


class ModelDeletion(BaseDeletion):

    def __init__(self, app_label, model_name, domain_filter_kwarg):
        super(ModelDeletion, self).__init__(app_label)
        self.domain_filter_kwarg = domain_filter_kwarg
        self.model_name = model_name

    def get_model_class(self):
        return apps.get_model(self.app_label, self.model_name)

    def execute(self, domain_name):
        if not domain_name:
            # The Django orm will properly turn a None domain_name to a
            # IS NULL filter. We don't want to allow deleting records for
            # NULL domain names since they might have special meaning (like
            # in some of the SMS models).
            raise RuntimeError("Expected a valid domain name")
        if self.is_app_installed():
            model = self.get_model_class()
            model.objects.filter(**{self.domain_filter_kwarg: domain_name}).delete()


def _delete_domain_backend_mappings(domain_name):
    model = apps.get_model('sms', 'SQLMobileBackendMapping')
    model.objects.filter(is_global=False, domain=domain_name).delete()


def _delete_domain_backends(domain_name):
    model = apps.get_model('sms', 'SQLMobileBackend')
    model.objects.filter(is_global=False, domain=domain_name).delete()


def _delete_web_user_membership(domain_name):
    from corehq.apps.users.models import WebUser
    active_web_users = WebUser.by_domain(domain_name)
    inactive_web_users = WebUser.by_domain(domain_name, is_active=False)
    for web_user in list(active_web_users) + list(inactive_web_users):
        web_user.delete_domain_membership(domain_name)
        web_user.save()


def _terminate_subscriptions(domain_name):
    today = date.today()

    with transaction.atomic():
        current_subscription = Subscription.get_active_subscription_by_domain(domain_name)

        if current_subscription:
            current_subscription.date_end = today
            current_subscription.is_active = False
            current_subscription.save()

            current_subscription.transfer_credits()

            _, downgraded_privs, upgraded_privs = get_change_status(current_subscription.plan_version, None)
            current_subscription.subscriber.deactivate_subscription(
                downgraded_privileges=downgraded_privs,
                upgraded_privileges=upgraded_privs,
                old_subscription=current_subscription,
                new_subscription=None,
            )

        Subscription.visible_objects.filter(
            Q(date_start__gt=today) | Q(date_start=today, is_active=False),
            subscriber__domain=domain_name,
        ).update(is_hidden_to_ops=True)


def _delete_all_cases(domain_name):
    logger.info('Deleting cases...')
    case_accessor = CaseAccessors(domain_name)
    case_ids = case_accessor.get_case_ids_in_domain()
    for case_id_chunk in chunked(with_progress_bar(case_ids, stream=silence_during_tests()), 500):
        case_accessor.soft_delete_cases(list(case_id_chunk))
    logger.info('Deleting cases complete.')


def _delete_all_forms(domain_name):
    logger.info('Deleting forms...')
    form_accessor = FormAccessors(domain_name)
    form_ids = list(itertools.chain(*[
        form_accessor.get_all_form_ids_in_domain(doc_type=doc_type)
        for doc_type in doc_type_to_state
    ]))
    for form_id_chunk in chunked(with_progress_bar(form_ids, stream=silence_during_tests()), 500):
        form_accessor.soft_delete_forms(list(form_id_chunk))
    logger.info('Deleting forms complete.')


def _delete_data_files(domain_name):
    db = get_db_alias_for_partitioned_doc(domain_name)
    get_blob_db().bulk_delete(metas=list(BlobMeta.objects.using(db).filter(
        parent_id=domain_name,
        type_code=CODES.data_file,
    )))


def _delete_custom_data_fields(domain_name):
    # The CustomDataFieldsDefinition instances are cleaned up as part of the
    # bulk couch delete, but we also need to clear the cache
    logger.info('Deleting custom data fields...')
    for field_view in [LocationFieldsView, ProductFieldsView, UserFieldsView]:
        get_by_domain_and_type.clear(domain_name, field_view.field_type)
    logger.info('Deleting custom data fields complete.')


# We use raw queries instead of ORM because Django queryset delete needs to
# fetch objects into memory to send signals and handle cascades. It makes deletion very slow
# if we have a millions of rows in stock data tables.
DOMAIN_DELETE_OPERATIONS = [
    RawDeletion('stock', """
        DELETE FROM stock_stocktransaction
        WHERE report_id IN (SELECT id FROM stock_stockreport WHERE domain=%s)
    """),
    RawDeletion('stock', "DELETE FROM stock_stockreport WHERE domain=%s"),
    RawDeletion('stock', """
        DELETE FROM commtrack_stockstate
        WHERE product_id IN (SELECT product_id FROM products_sqlproduct WHERE domain=%s)
    """),
    ModelDeletion('products', 'SQLProduct', 'domain'),
    ModelDeletion('locations', 'SQLLocation', 'domain'),
    ModelDeletion('locations', 'LocationType', 'domain'),
    ModelDeletion('stock', 'DocDomainMapping', 'domain_name'),
    ModelDeletion('domain_migration_flags', 'DomainMigrationProgress', 'domain'),
    ModelDeletion('sms', 'DailyOutboundSMSLimitReached', 'domain'),
    ModelDeletion('sms', 'SMS', 'domain'),
    ModelDeletion('sms', 'SQLLastReadMessage', 'domain'),
    ModelDeletion('sms', 'ExpectedCallback', 'domain'),
    ModelDeletion('ivr', 'Call', 'domain'),
    ModelDeletion('sms', 'Keyword', 'domain'),
    ModelDeletion('sms', 'PhoneNumber', 'domain'),
    ModelDeletion('sms', 'MessagingSubEvent', 'parent__domain'),
    ModelDeletion('sms', 'MessagingEvent', 'domain'),
    ModelDeletion('sms', 'QueuedSMS', 'domain'),
    ModelDeletion('sms', 'SelfRegistrationInvitation', 'domain'),
    CustomDeletion('sms', _delete_domain_backend_mappings),
    ModelDeletion('sms', 'MobileBackendInvitation', 'domain'),
    CustomDeletion('sms', _delete_domain_backends),
    CustomDeletion('users', _delete_web_user_membership),
    CustomDeletion('accounting', _terminate_subscriptions),
    CustomDeletion('form_processor', _delete_all_cases),
    CustomDeletion('form_processor', _delete_all_forms),
    ModelDeletion('aggregate_ucrs', 'AggregateTableDefinition', 'domain'),
    ModelDeletion('case_importer', 'CaseUploadRecord', 'domain'),
    ModelDeletion('case_search', 'CaseSearchConfig', 'domain'),
    ModelDeletion('case_search', 'CaseSearchQueryAddition', 'domain'),
    ModelDeletion('case_search', 'FuzzyProperties', 'domain'),
    ModelDeletion('case_search', 'IgnorePatterns', 'domain'),
    ModelDeletion('data_analytics', 'GIRRow', 'domain_name'),
    ModelDeletion('data_analytics', 'MALTRow', 'domain_name'),
    ModelDeletion('data_dictionary', 'CaseType', 'domain'),
    ModelDeletion('data_interfaces', 'CaseRuleAction', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleCriteria', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleSubmission', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleSubmission', 'domain'),  # TODO
    ModelDeletion('data_interfaces', 'AutomaticUpdateRule', 'domain'),
    ModelDeletion('data_interfaces', 'DomainCaseRuleRun', 'domain'),
    ModelDeletion('domain', 'TransferDomainRequest', 'domain'),
    ModelDeletion('export', 'EmailExportWhenDoneRequest', 'domain'),
    CustomDeletion('export', _delete_data_files),
    ModelDeletion('locations', 'LocationFixtureConfiguration', 'domain'),
    ModelDeletion('ota', 'MobileRecoveryMeasure', 'domain'),
    ModelDeletion('ota', 'SerialIdBucket', 'domain'),
    ModelDeletion('phone', 'OwnershipCleanlinessFlag', 'domain'),
    ModelDeletion('phone', 'SyncLogSQL', 'domain'),
    ModelDeletion('reminders', 'EmailUsage', 'domain'),
    ModelDeletion('reports', 'ReportsSidebarOrdering', 'domain'),
    ModelDeletion('smsforms', 'SQLXFormsSession', 'domain'),
    ModelDeletion('userreports', 'AsyncIndicator', 'domain'),
    ModelDeletion('users', 'DomainRequest', 'domain'),
    ModelDeletion('zapier', 'ZapierSubscription', 'domain'),
    ModelDeletion('motech', 'RequestLog', 'domain'),
    ModelDeletion('couchforms', 'UnfinishedSubmissionStub', 'domain'),
    CustomDeletion('custom_data_fields', _delete_custom_data_fields),
    CustomDeletion('ucr', delete_all_ucr_tables_for_domain),
]


def apply_deletion_operations(domain_name, dynamic_operations):
    all_ops = dynamic_operations or []
    all_ops.extend(DOMAIN_DELETE_OPERATIONS)
    raw_ops, model_ops = _split_ops_by_type(all_ops)

    with connection.cursor() as cursor:
        for op in raw_ops:
            op.execute(cursor, domain_name)

    for op in model_ops:
        op.execute(domain_name)


def _split_ops_by_type(ops):
    raw_ops = []
    model_ops = []
    for op in ops:
        if isinstance(op, RawDeletion):
            raw_ops.append(op)
        else:
            model_ops.append(op)
    return raw_ops, model_ops
