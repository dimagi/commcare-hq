import logging
from datetime import date

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from field_audit.models import AuditAction

from dimagi.utils.chunked import chunked

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import get_change_status
from corehq.apps.domain.utils import silence_during_tests
from corehq.apps.es import CaseES, CaseSearchES, FormES
from corehq.apps.userreports.dbaccessors import (
    delete_all_ucr_tables_for_domain,
)
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
from corehq.apps.users.util import SYSTEM_USER_ID, log_user_change
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.elastic import ESError
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.util import (
    get_db_aliases_for_partitioned_query,
    paginate_query_across_partitioned_databases, estimate_partitioned_row_count,
)
from corehq.util.log import with_progress_bar
from settings import HQ_ACCOUNT_ROOT

logger = logging.getLogger(__name__)


class BaseDeletion(object):

    def __init__(self, app_label, models):
        self.app_label = app_label
        self.models = models

    def get_model_classes(self):
        model_classes = []
        for model_name in self.models:
            if '.' in model_name:
                model_class = apps.get_model(model_name)
            else:
                model_class = apps.get_model(self.app_label, model_name)
            model_classes.append(model_class)
        return model_classes

    def is_app_installed(self):
        try:
            return bool(apps.get_app_config(self.app_label))
        except LookupError:
            return False


class CustomDeletion(BaseDeletion):

    def __init__(self, app_label, deletion_fn, models):
        super(CustomDeletion, self).__init__(app_label, models)
        self.deletion_fn = deletion_fn

    def execute(self, domain_name):
        if self.is_app_installed():
            self.deletion_fn(domain_name)


class ModelDeletion(BaseDeletion):

    def __init__(self, app_label, model_name, domain_filter_kwarg, extra_models=None, audit_action=None):
        """Deletes all records of an app model matching the provided domain
        filter.

        :param app_label: label of the app containing the model(s)
        :param model_name: name of the model in the app
        :param domain_filter_kwarg: name of the model field to filter by domain
        :param extra_models: (optional) a collection of other models in the same
            app which will be deleted along with ``model_name`` via cascaded deletion.
            The ``extra_models`` is used only for auditing purposes.
        :param audit_action: (optional) an audit action to be provided as a
            keyword argument when deleting records (e.g.
            ``<QuerySet>.delete(audit_action=audit_action)``). Necessary for
            models whose manager is an instance of
            ``field_audit.models.AuditingManager``. The default (``None``)
            results in ``<QuerySet>.delete()`` being called without parameters.
        """
        models = extra_models or []
        models.append(model_name)
        super(ModelDeletion, self).__init__(app_label, models)
        self.domain_filter_kwarg = domain_filter_kwarg
        self.model_name = model_name
        self.delete_kwargs = {} if audit_action is None else {"audit_action": audit_action}

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
            model.objects.filter(**{self.domain_filter_kwarg: domain_name}).delete(**self.delete_kwargs)


class PartitionedModelDeletion(ModelDeletion):
    def execute(self, domain_name):
        if not self.is_app_installed():
            return
        model = self.get_model_class()
        for db_name in get_db_aliases_for_partitioned_query():
            model.objects.using(db_name).filter(**{self.domain_filter_kwarg: domain_name}).delete()


class DjangoUserRelatedModelDeletion(ModelDeletion):
    def execute(self, domain_name):
        if not self.is_app_installed():
            return
        model = self.get_model_class()
        filter_kwarg = f"{self.domain_filter_kwarg}__contains"
        total, counts = model.objects.filter(**{filter_kwarg: f"@{domain_name}.commcarehq.org"}).delete()
        logger.info("Deleted %s %s", total, self.model_name)
        logger.info(counts)


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
        if settings.UNIT_TESTING and not web_user.domain_memberships:
            web_user.delete(domain_name, deleted_by=None)
        else:
            web_user.save()
            _log_web_user_membership_removed(web_user, domain_name, __name__ + "._delete_web_user_membership")


def _log_web_user_membership_removed(user, domain, via):
    log_user_change(by_domain=None, for_domain=domain, couch_user=user,
                    changed_by_user=SYSTEM_USER_ID, changed_via=via,
                    change_messages=UserChangeMessage.domain_removal(domain))


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


def delete_all_cases(domain_name):
    logger.info('Deleting cases...')
    case_ids = iter_ids(CommCareCase, 'case_id', domain_name)
    for chunk in chunked(case_ids, 1000, list):
        CommCareCase.objects.hard_delete_cases(domain_name, chunk, publish_changes=False)
    _delete_es_docs(CaseES, domain_name)
    _delete_es_docs(CaseSearchES, domain_name)
    logger.info('Deleting cases complete.')


def delete_all_forms(domain_name):
    logger.info('Deleting forms...')
    form_ids = iter_ids(XFormInstance, 'form_id', domain_name)
    for chunk in chunked(form_ids, 1000, list):
        XFormInstance.objects.hard_delete_forms(domain_name, chunk, publish_changes=False)
    _delete_es_docs(FormES, domain_name)
    logger.info('Deleting forms complete.')


def iter_ids(model_class, field, domain, chunk_size=1000):
    where = Q(domain=domain)
    rows = paginate_query_across_partitioned_databases(
        model_class,
        where,
        values=[field],
        load_source='delete_domain',
        query_size=chunk_size,
    )
    with silence_during_tests() as stream:
        yield from with_progress_bar(
            (r[0] for r in rows),
            estimate_partitioned_row_count(model_class, where),
            prefix="",
            oneline="concise",
            stream=stream,
        )


def _delete_es_docs(es_query, domain_name):
    query = es_query().domain(domain_name)
    with silence_during_tests() as stream:
        doc_ids = with_progress_bar(
            query.scroll_ids(),
            query.count(),
            prefix=es_query.__name__,
            oneline="concise",
            stream=stream,
        )
        for chunk in chunked(doc_ids, 1000, list):
            query.adapter.bulk_delete(chunk)


def _delete_data_files(domain_name):
    get_blob_db().bulk_delete(metas=list(BlobMeta.objects.partitioned_query(domain_name).filter(
        parent_id=domain_name,
        type_code=CODES.data_file,
    )))


def _delete_sms_content_events_schedules(domain_name):
    models = [
        'SMSContent', 'EmailContent', 'SMSSurveyContent',
        'IVRSurveyContent', 'SMSCallbackContent', 'CustomContent',
        'FCMNotificationContent'
    ]
    filters = [
        'alertevent__schedule__domain',
        'timedevent__schedule__domain',
        'randomtimedevent__schedule__domain',
        'casepropertytimedevent__schedule__domain'
    ]
    _delete_filtered_models('scheduling', models, [
        Q(**{name: domain_name}) for name in filters
    ])


def _delete_django_users(domain_name):
    total, counts = User.objects.filter(
        username__contains=f"@{domain_name}.{HQ_ACCOUNT_ROOT}"
    ).delete()
    logger.info("Deleted %s Django users", total)
    logger.info(counts)


def _delete_filtered_models(app_name, models, domain_filters):
    for model_name in models:
        model = apps.get_model(app_name, model_name)
        for q_filter in domain_filters:
            total, counts = model.objects.filter(q_filter).delete()
            if total:
                logger.info("Deleted %s", counts)


def _delete_demo_user_restores(domain_name):
    from corehq.apps.ota.models import DemoUserRestore
    from corehq.apps.users.dbaccessors import get_practice_mode_mobile_workers
    try:
        users = get_practice_mode_mobile_workers(domain_name)
    except ESError:
        # Fallback in case of ES Error
        users = get_all_commcare_users_by_domain(domain_name)

    for user in users:
        if getattr(user, "demo_restore_id", None):
            try:
                DemoUserRestore.objects.get(id=user.demo_restore_id).delete()
            except DemoUserRestore.DoesNotExist:
                pass


# We use raw queries instead of ORM because Django queryset delete needs to
# fetch objects into memory to send signals and handle cascades. It makes deletion very slow
# if we have a millions of rows in stock data tables.
DOMAIN_DELETE_OPERATIONS = [
    DjangoUserRelatedModelDeletion('otp_static', 'StaticDevice', 'user__username', ['StaticToken']),
    DjangoUserRelatedModelDeletion('otp_totp', 'TOTPDevice', 'user__username'),
    DjangoUserRelatedModelDeletion('two_factor', 'PhoneDevice', 'user__username'),
    DjangoUserRelatedModelDeletion('users', 'HQApiKey', 'user__username'),
    CustomDeletion('auth', _delete_django_users, ['User']),
    ModelDeletion('products', 'SQLProduct', 'domain'),
    ModelDeletion('locations', 'SQLLocation', 'domain'),
    ModelDeletion('locations', 'LocationType', 'domain'),
    ModelDeletion('domain', 'AllowedUCRExpressionSettings', 'domain'),
    ModelDeletion('domain_migration_flags', 'DomainMigrationProgress', 'domain'),
    ModelDeletion('sms', 'DailyOutboundSMSLimitReached', 'domain'),
    ModelDeletion('sms', 'SMS', 'domain'),
    ModelDeletion('sms', 'Email', 'domain'),
    ModelDeletion('sms', 'SQLLastReadMessage', 'domain'),
    ModelDeletion('sms', 'ExpectedCallback', 'domain'),
    ModelDeletion('ivr', 'Call', 'domain'),
    ModelDeletion('sms', 'Keyword', 'domain', ['KeywordAction']),
    ModelDeletion('sms', 'PhoneNumber', 'domain'),
    ModelDeletion('sms', 'MessagingSubEvent', 'domain'),
    ModelDeletion('sms', 'MessagingEvent', 'domain'),
    ModelDeletion('sms', 'QueuedSMS', 'domain'),
    ModelDeletion('sms', 'PhoneBlacklist', 'domain'),
    CustomDeletion('sms', _delete_domain_backend_mappings, ['SQLMobileBackendMapping']),
    ModelDeletion('sms', 'MobileBackendInvitation', 'domain'),
    CustomDeletion('sms', _delete_domain_backends, ['SQLMobileBackend']),
    CustomDeletion('users', _delete_web_user_membership, []),
    CustomDeletion('accounting', _terminate_subscriptions, ['Subscription']),
    CustomDeletion('form_processor', delete_all_cases, ['CommCareCase']),
    CustomDeletion('form_processor', delete_all_forms, ['XFormInstance']),
    ModelDeletion('aggregate_ucrs', 'AggregateTableDefinition', 'domain', [
        'PrimaryColumn', 'SecondaryColumn', 'SecondaryTableDefinition', 'TimeAggregationDefinition',
    ]),
    ModelDeletion('app_manager', 'AppReleaseByLocation', 'domain'),
    ModelDeletion('app_manager', 'LatestEnabledBuildProfiles', 'domain'),
    ModelDeletion('app_manager', 'ResourceOverride', 'domain'),
    ModelDeletion('app_manager', 'GlobalAppConfig', 'domain'),
    ModelDeletion('app_manager', 'ApplicationReleaseLog', 'domain'),
    ModelDeletion('case_importer', 'CaseUploadRecord', 'domain', [
        'CaseUploadFileMeta', 'CaseUploadFormRecord'
    ]),
    ModelDeletion('case_search', 'DomainsNotInCaseSearchIndex', 'domain'),
    ModelDeletion('case_search', 'CaseSearchConfig', 'domain'),
    ModelDeletion('case_search', 'FuzzyProperties', 'domain'),
    ModelDeletion('case_search', 'IgnorePatterns', 'domain'),
    ModelDeletion('cloudcare', 'ApplicationAccess', 'domain', ['SQLAppGroup']),
    ModelDeletion('commtrack', 'CommtrackConfig', 'domain', [
        'ActionConfig', 'AlertConfig', 'ConsumptionConfig',
        'StockLevelsConfig', 'StockRestoreConfig',
    ]),
    ModelDeletion('consumption', 'DefaultConsumption', 'domain'),
    ModelDeletion('users', 'SQLUserData', 'domain'),
    ModelDeletion('custom_data_fields', 'CustomDataFieldsDefinition', 'domain', [
        'CustomDataFieldsProfile', 'Field',
    ]),
    ModelDeletion('data_analytics', 'GIRRow', 'domain_name'),
    ModelDeletion('data_analytics', 'MALTRow', 'domain_name'),
    ModelDeletion('data_dictionary', 'CaseType', 'domain', [
        'CaseProperty',
        'CasePropertyGroup',
        'CasePropertyAllowedValue',
        'fhir.FHIRResourceType',
        'fhir.FHIRResourceProperty',
    ]),
    ModelDeletion('scheduling', 'MigratedReminder', 'rule__domain'),
    ModelDeletion('data_interfaces', 'ClosedParentDefinition', 'caserulecriteria__rule__domain'),
    ModelDeletion('data_interfaces', 'CustomMatchDefinition', 'caserulecriteria__rule__domain'),
    ModelDeletion('data_interfaces', 'MatchPropertyDefinition', 'caserulecriteria__rule__domain'),
    ModelDeletion('data_interfaces', 'LocationFilterDefinition', 'caserulecriteria__rule__domain'),
    ModelDeletion('data_interfaces', 'UCRFilterDefinition', 'caserulecriteria__rule__domain'),
    ModelDeletion('data_interfaces', 'CustomActionDefinition', 'caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'UpdateCaseDefinition', 'caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'CaseDuplicate', 'action__caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'CaseDuplicateNew', 'action__caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'CaseDeduplicationActionDefinition', 'caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'CreateScheduleInstanceActionDefinition', 'caseruleaction__rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleAction', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleCriteria', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleSubmission', 'rule__domain'),
    ModelDeletion('data_interfaces', 'CaseRuleSubmission', 'domain'),  # TODO
    ModelDeletion('data_interfaces', 'AutomaticUpdateRule', 'domain', audit_action=AuditAction.AUDIT),
    ModelDeletion('data_interfaces', 'DomainCaseRuleRun', 'domain'),
    ModelDeletion('integration', 'DialerSettings', 'domain'),
    ModelDeletion('integration', 'GaenOtpServerSettings', 'domain'),
    ModelDeletion('integration', 'HmacCalloutSettings', 'domain'),
    ModelDeletion('integration', 'SimprintsIntegration', 'domain'),
    ModelDeletion('linked_domain', 'DomainLink', 'linked_domain', ['DomainLinkHistory']),
    CustomDeletion('scheduling', _delete_sms_content_events_schedules, [
        'SMSContent', 'EmailContent', 'SMSSurveyContent',
        'IVRSurveyContent', 'SMSCallbackContent', 'CustomContent', 'FCMNotificationContent'
    ]),
    ModelDeletion('scheduling', 'MigratedReminder', 'broadcast__domain'),
    ModelDeletion('scheduling', 'AlertEvent', 'schedule__domain'),
    ModelDeletion('scheduling', 'TimedEvent', 'schedule__domain'),
    ModelDeletion('scheduling', 'RandomTimedEvent', 'schedule__domain'),
    ModelDeletion('scheduling', 'CasePropertyTimedEvent', 'schedule__domain'),
    ModelDeletion('scheduling', 'AlertSchedule', 'domain'),
    ModelDeletion('scheduling', 'ScheduledBroadcast', 'domain'),
    ModelDeletion('scheduling', 'ImmediateBroadcast', 'domain'),
    ModelDeletion('scheduling', 'TimedSchedule', 'domain'),
    PartitionedModelDeletion('scheduling_partitioned', 'AlertScheduleInstance', 'domain'),
    PartitionedModelDeletion('scheduling_partitioned', 'CaseAlertScheduleInstance', 'domain'),
    PartitionedModelDeletion('scheduling_partitioned', 'CaseTimedScheduleInstance', 'domain'),
    PartitionedModelDeletion('scheduling_partitioned', 'TimedScheduleInstance', 'domain'),
    ModelDeletion('domain', 'TransferDomainRequest', 'domain'),
    ModelDeletion('export', 'EmailExportWhenDoneRequest', 'domain'),
    ModelDeletion('export', 'LedgerSectionEntry', 'domain'),
    CustomDeletion('export', _delete_data_files, []),
    ModelDeletion('geospatial', 'GeoPolygon', 'domain'),
    ModelDeletion('locations', 'LocationFixtureConfiguration', 'domain'),
    ModelDeletion('ota', 'MobileRecoveryMeasure', 'domain'),
    ModelDeletion('ota', 'SerialIdBucket', 'domain'),
    ModelDeletion('ota', 'DeviceLogRequest', 'domain'),
    ModelDeletion('phone', 'SyncLogSQL', 'domain'),
    CustomDeletion('ota', _delete_demo_user_restores, ['DemoUserRestore']),
    ModelDeletion('phonelog', 'ForceCloseEntry', 'domain'),
    ModelDeletion('phonelog', 'UserErrorEntry', 'domain'),
    ModelDeletion('registration', 'RegistrationRequest', 'domain'),
    ModelDeletion('reminders', 'EmailUsage', 'domain'),
    ModelDeletion('registry', 'DataRegistry', 'domain', [
        'RegistryInvitation', 'RegistryGrant', 'RegistryAuditLog'
    ]),
    ModelDeletion('registry', 'RegistryGrant', 'from_domain'),
    ModelDeletion('registry', 'RegistryInvitation', 'domain'),
    ModelDeletion('reports', 'TableauServer', 'domain'),
    ModelDeletion('reports', 'TableauVisualization', 'domain'),
    ModelDeletion('reports', 'TableauConnectedApp', 'server__domain'),
    ModelDeletion('reports', 'TableauUser', 'server__domain'),
    ModelDeletion('reports', 'QueryStringHash', 'domain'),
    ModelDeletion('smsforms', 'SQLXFormsSession', 'domain'),
    ModelDeletion('translations', 'TransifexOrganization', 'transifexproject__domain'),
    ModelDeletion('translations', 'SMSTranslations', 'domain'),
    ModelDeletion('translations', 'TransifexBlacklist', 'domain'),
    ModelDeletion('translations', 'TransifexProject', 'domain'),
    ModelDeletion(
        'generic_inbound', 'ConfigurableAPI', 'domain',
        extra_models=["ConfigurableApiValidation", "RequestLog", "ProcessingAttempt"],
        audit_action=AuditAction.AUDIT
    ),
    ModelDeletion('userreports', 'AsyncIndicator', 'domain'),
    ModelDeletion('userreports', 'DataSourceActionLog', 'domain'),
    ModelDeletion('userreports', 'InvalidUCRData', 'domain'),
    ModelDeletion('userreports', 'UCRExpression', 'domain'),
    ModelDeletion('users', 'ConnectIDUserLink', 'domain'),
    ModelDeletion('users', 'DomainRequest', 'domain'),
    ModelDeletion('users', 'DeactivateMobileWorkerTrigger', 'domain'),
    ModelDeletion('users', 'Invitation', 'domain'),
    ModelDeletion('users', 'UserReportingMetadataStaging', 'domain'),
    ModelDeletion('users', 'UserRole', 'domain', [
        'RolePermission', 'RoleAssignableBy', 'Permission'
    ], audit_action=AuditAction.AUDIT),
    ModelDeletion('user_importer', 'UserUploadRecord', 'domain'),
    ModelDeletion('zapier', 'ZapierSubscription', 'domain'),
    ModelDeletion('dhis2', 'SQLDataValueMap', 'dataset_map__domain'),
    ModelDeletion('dhis2', 'SQLDataSetMap', 'domain'),
    ModelDeletion('motech', 'RequestLog', 'domain'),
    ModelDeletion('fhir', 'FHIRImportConfig', 'domain', [
        'FHIRImportResourceType', 'ResourceTypeRelationship',
        'FHIRImportResourceProperty',
    ]),
    ModelDeletion('repeaters', 'Repeater', 'domain'),
    ModelDeletion('motech', 'ConnectionSettings', 'domain'),
    ModelDeletion('couchforms', 'UnfinishedSubmissionStub', 'domain'),
    ModelDeletion('couchforms', 'UnfinishedArchiveStub', 'domain'),
    ModelDeletion('fixtures', 'LookupTable', 'domain'),
    CustomDeletion('ucr', delete_all_ucr_tables_for_domain, []),
    ModelDeletion('domain', 'OperatorCallLimitSettings', 'domain'),
    ModelDeletion('domain', 'SMSAccountConfirmationSettings', 'domain'),
    ModelDeletion('domain', 'AppReleaseModeSetting', 'domain'),
    ModelDeletion('events', 'Event', 'domain'),
    ModelDeletion('events', 'AttendanceTrackingConfig', 'domain'),
    ModelDeletion('geospatial', 'GeoConfig', 'domain'),
    ModelDeletion('email', 'EmailSettings', 'domain'),
    ModelDeletion('hqmedia', 'LogoForSystemEmailsReference', 'domain'),
]


def apply_deletion_operations(domain_name):
    for op in DOMAIN_DELETE_OPERATIONS:
        op.execute(domain_name)
