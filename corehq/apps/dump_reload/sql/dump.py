from collections import Counter, OrderedDict, defaultdict

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import router

from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from corehq.apps.dump_reload.sql.filters import (
    FilteredModelIteratorBuilder,
    ManyFilters,
    MultimediaBlobMetaFilter,
    SimpleFilter,
    UnfilteredModelIteratorBuilder,
    UniqueFilteredModelIteratorBuilder,
    UserIDFilter,
    UsernameFilter,
)
from corehq.apps.dump_reload.sql.serialization import JsonLinesSerializer
from corehq.apps.dump_reload.util import get_model_class, get_model_label
from corehq.sql_db.config import plproxy_config

APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP = defaultdict(list)
[APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP[iterator.model_label].append(iterator) for iterator in [
    FilteredModelIteratorBuilder('locations.LocationType', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('locations.SQLLocation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('blobs.BlobMeta', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('blobs.BlobMeta', MultimediaBlobMetaFilter()),

    FilteredModelIteratorBuilder('form_processor.XFormInstance', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.XFormOperation', SimpleFilter('form__domain')),

    FilteredModelIteratorBuilder('form_processor.CommCareCase', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.CommCareCaseIndex', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.CaseAttachment', SimpleFilter('case__domain')),
    FilteredModelIteratorBuilder('form_processor.CaseTransaction', SimpleFilter('case__domain')),
    FilteredModelIteratorBuilder('form_processor.LedgerValue', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.LedgerTransaction', SimpleFilter('case__domain')),

    FilteredModelIteratorBuilder('case_search.DomainsNotInCaseSearchIndex', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('case_search.CaseSearchConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('case_search.FuzzyProperties', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('case_search.IgnorePatterns', SimpleFilter('domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent', SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent', SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSCallbackContent',
                                       SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSCallbackContent',
                                       SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSCallbackContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSCallbackContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.EmailContent', SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.EmailContent', SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.EmailContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.EmailContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSSurveyContent',
                                       SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSSurveyContent',
                                       SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSSurveyContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSSurveyContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.IVRSurveyContent',
                                       SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.IVRSurveyContent',
                                       SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.IVRSurveyContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.IVRSurveyContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.CustomContent', SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.CustomContent', SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.CustomContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.CustomContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.FCMNotificationContent',
                                       SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.FCMNotificationContent',
                                       SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.FCMNotificationContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.FCMNotificationContent',
                                       SimpleFilter('casepropertytimedevent__schedule__domain')),
    FilteredModelIteratorBuilder('scheduling.AlertSchedule', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling.AlertEvent', SimpleFilter('schedule__domain')),
    FilteredModelIteratorBuilder('scheduling.ImmediateBroadcast', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling.TimedSchedule', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling.TimedEvent', SimpleFilter('schedule__domain')),
    FilteredModelIteratorBuilder('scheduling.RandomTimedEvent', SimpleFilter('schedule__domain')),
    FilteredModelIteratorBuilder('scheduling.CasePropertyTimedEvent', SimpleFilter('schedule__domain')),
    FilteredModelIteratorBuilder('scheduling.ScheduledBroadcast', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling_partitioned.AlertScheduleInstance', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling_partitioned.CaseAlertScheduleInstance', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling_partitioned.CaseTimedScheduleInstance', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('scheduling_partitioned.TimedScheduleInstance', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('custom_data_fields.CustomDataFieldsDefinition', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('custom_data_fields.CustomDataFieldsProfile', SimpleFilter('definition__domain')),
    FilteredModelIteratorBuilder('custom_data_fields.Field', SimpleFilter('definition__domain')),
    FilteredModelIteratorBuilder('data_interfaces.AutomaticUpdateRule', SimpleFilter('domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.ClosedParentDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.CustomMatchDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.MatchPropertyDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.LocationFilterDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.CustomActionDefinition',
                                       SimpleFilter('caseruleaction__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.UpdateCaseDefinition',
                                       SimpleFilter('caseruleaction__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.UCRFilterDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CreateScheduleInstanceActionDefinition',
                                 SimpleFilter('caseruleaction__rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseDeduplicationActionDefinition',
                                 SimpleFilter('caseruleaction__rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleAction', SimpleFilter('rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleCriteria', SimpleFilter('rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleSubmission', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_interfaces.DomainCaseRuleRun', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('auth.User', UsernameFilter()),
    FilteredModelIteratorBuilder('integration.DialerSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('integration.GaenOtpServerSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('integration.HmacCalloutSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('integration.SimprintsIntegration', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.DeviceReportEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.ForceCloseEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.UserErrorEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.UserEntry', UserIDFilter('user_id')),
    FilteredModelIteratorBuilder('ota.DemoUserRestore', UserIDFilter('demo_user_id', include_web_users=False)),
    FilteredModelIteratorBuilder('ota.DeviceLogRequest', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('ota.MobileRecoveryMeasure', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('ota.SerialIdBucket', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain_migration_flags.DomainMigrationProgress', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('products.SQLProduct', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('reports.TableauServer', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('reports.TableauVisualization', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('reports.TableauConnectedApp', SimpleFilter('server__domain')),
    FilteredModelIteratorBuilder('reports.TableauUser', SimpleFilter('server__domain')),
    FilteredModelIteratorBuilder('reports.QueryStringHash', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('smsforms.SQLXFormsSession', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.MessagingEvent', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.MessagingSubEvent', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.PhoneNumber', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SMS', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.Keyword', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.KeywordAction', SimpleFilter('keyword__domain')),
    FilteredModelIteratorBuilder('sms.QueuedSMS', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SQLMobileBackend', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SQLMobileBackendMapping', ManyFilters('domain', 'backend__domain')),
    FilteredModelIteratorBuilder('cloudcare.ApplicationAccess', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('cloudcare.SQLAppGroup', SimpleFilter('application_access__domain')),
    FilteredModelIteratorBuilder('linked_domain.DomainLink', SimpleFilter('linked_domain')),
    FilteredModelIteratorBuilder('linked_domain.DomainLinkHistory', SimpleFilter('link__linked_domain')),
    FilteredModelIteratorBuilder('user_importer.UserUploadRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.ConnectIDUserLink', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.DeactivateMobileWorkerTrigger', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.DomainRequest', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.Invitation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.RoleAssignableBy', SimpleFilter('role__domain')),
    FilteredModelIteratorBuilder('users.RolePermission', SimpleFilter('role__domain')),
    FilteredModelIteratorBuilder('users.UserRole', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('users.SQLUserData', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('locations.LocationFixtureConfiguration', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('commtrack.CommtrackConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('commtrack.ActionConfig', SimpleFilter('commtrack_config__domain')),
    FilteredModelIteratorBuilder('commtrack.AlertConfig', SimpleFilter('commtrack_config__domain')),
    FilteredModelIteratorBuilder('commtrack.ConsumptionConfig', SimpleFilter('commtrack_config__domain')),
    FilteredModelIteratorBuilder('commtrack.StockLevelsConfig', SimpleFilter('commtrack_config__domain')),
    FilteredModelIteratorBuilder('commtrack.StockRestoreConfig', SimpleFilter('commtrack_config__domain')),
    FilteredModelIteratorBuilder('consumption.DefaultConsumption', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_dictionary.CaseType', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_dictionary.CaseProperty', SimpleFilter('case_type__domain')),
    FilteredModelIteratorBuilder('data_dictionary.CasePropertyGroup', SimpleFilter('case_type__domain')),
    FilteredModelIteratorBuilder('data_dictionary.CasePropertyAllowedValue',
                                 SimpleFilter('case_property__case_type__domain')),
    FilteredModelIteratorBuilder('fhir.FHIRResourceType', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('fhir.FHIRResourceProperty', SimpleFilter('resource_type__domain')),
    FilteredModelIteratorBuilder('app_manager.GlobalAppConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.AppReleaseByLocation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.LatestEnabledBuildProfiles', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.ApplicationReleaseLog', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.ResourceOverride', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadFileMeta', SimpleFilter('caseuploadrecord__domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadFormRecord', SimpleFilter('case_upload_record__domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('repeaters.Repeater', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('motech.ConnectionSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('motech.RequestLog', SimpleFilter('domain')),
    # NH (2021-01-08): Including RepeatRecord because we dump (Couch)
    # RepeatRecord, but this does not seem like a good idea.
    FilteredModelIteratorBuilder('repeaters.RepeatRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('repeaters.RepeatRecordAttempt', SimpleFilter('repeat_record__domain')),
    FilteredModelIteratorBuilder('saved_reports.ScheduledReportLog', SimpleFilter('domain')),
    UnfilteredModelIteratorBuilder('saved_reports.ScheduledReportsCheckpoint'),
    FilteredModelIteratorBuilder('translations.SMSTranslations', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('translations.TransifexBlacklist', SimpleFilter('domain')),
    UniqueFilteredModelIteratorBuilder(
        'translations.TransifexOrganization', SimpleFilter('transifexproject__domain')),
    FilteredModelIteratorBuilder('translations.TransifexProject', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('zapier.ZapierSubscription', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.AllowedUCRExpressionSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.DomainAuditRecordEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.OperatorCallLimitSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.ProjectLimit', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.SMSAccountConfirmationSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.SuperuserProjectEntryRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('domain.TransferDomainRequest', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('export.LedgerSectionEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('fixtures.LookupTable', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('fixtures.LookupTableRow', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('fixtures.LookupTableRowOwner', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('hqmedia.LogoForSystemEmailsReference', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('userreports.UCRExpression', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('generic_inbound.ConfigurableAPI', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('generic_inbound.ConfigurableApiValidation', SimpleFilter('api__domain')),
    FilteredModelIteratorBuilder('generic_inbound.RequestLog', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('generic_inbound.ProcessingAttempt', SimpleFilter('log__domain')),
    FilteredModelIteratorBuilder('geospatial.GeoPolygon', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('hqwebapp.Alert', SimpleFilter('created_by_domain')),
    FilteredModelIteratorBuilder('domain.AppReleaseModeSetting', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('events.Event', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('events.AttendanceTrackingConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('geospatial.GeoConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('email.EmailSettings', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('dhis2.SQLDataSetMap', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('dhis2.SQLDataValueMap', SimpleFilter('dataset_map__domain')),
]]


class SqlDataDumper(DataDumper):
    slug = 'sql'

    def dump(self, output_stream):
        """
        When serializing data using JsonLinesSerializer().serialize(...), the additional parameters are set for
        the following reasons:

        use_natural_primary_keys is necessary for sharded models to ensure the primary key, which will not be
        unique across shards, is not used. This can be thought of as "use natural primary keys when defined".

        use_natural_foreign_keys is necessary for foreign keys that reference primary keys on models that have a
        natural_key method defined. This can be thought of as "use natural foreign keys when defined". For example,
        SQLUserData has a foreign key to User based on the primary key. However a natural_key method is defined on
        the User model, so its primary key will not be serialized when use_natural_primary_keys=True. To resolve,
        we set use_natural_foreign_keys=True which will result in natural keys being serialized as part of the
        foreign key field when referencing a model with natural_key defined.
        """
        stats = Counter()
        objects = get_objects_to_dump(
            self.domain,
            self.excludes,
            self.includes,
            stats_counter=stats,
            stdout=self.stdout,
        )

        JsonLinesSerializer().serialize(
            objects,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
            stream=output_stream
        )
        return stats


def get_objects_to_dump(domain, excludes, includes, stats_counter=None, stdout=None):
    """
    :param domain: domain name to filter with
    :param app_list: List of (app_config, model_class) tuples to dump
    :param excluded_models: List of model_class classes to exclude
    :return: generator yielding models objects
    """
    builders = get_model_iterator_builders_to_dump(domain, excludes, includes)
    yield from get_objects_to_dump_from_builders(builders, stats_counter, stdout)


def get_objects_to_dump_from_builders(builders, stats_counter=None, stdout=None):
    if stats_counter is None:
        stats_counter = Counter()
    for model_class, builder in builders:
        model_label = get_model_label(model_class)
        for iterator in builder.iterators():
            for obj in iterator:
                stats_counter.update([model_label])
                yield obj
        if stdout:
            stdout.write('Dumped {} {}\n'.format(stats_counter[model_label], model_label))


def get_model_iterator_builders_to_dump(domain, excludes, includes, limit_to_db=None):
    """
    :param domain: domain name to filter with
    :param app_list: List of (app_config, model_class) tuples to dump
    :param excluded_models: List of model_class classes to exclude
    :return: generator yielding query sets
    """
    excluded_apps, excluded_models = get_apps_and_models(excludes)
    included_apps, included_models = get_apps_and_models(includes)
    app_config_models = _get_app_list(excluded_apps, included_apps)

    # Collate the objects to be serialized.
    for model_class in serializers.sort_dependencies(list(app_config_models.items())):
        if included_models and model_class not in included_models:
            continue
        if model_class in excluded_models:
            continue

        iterator_builders = APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP[get_model_label(model_class)]
        for model_class, builder in get_all_model_iterators_builders_for_domain(
            model_class, domain, iterator_builders, limit_to_db=limit_to_db
        ):
            yield model_class, builder


def get_all_model_iterators_builders_for_domain(model_class, domain, builders, limit_to_db=None):
    if settings.USE_PARTITIONED_DATABASE and hasattr(model_class, 'partition_attr'):
        using = plproxy_config.form_processing_dbs
    else:
        using = [router.db_for_read(model_class)]

    if limit_to_db:
        if limit_to_db not in using:
            raise DomainDumpError('DB specified is not valide for '
                                  'model class: {} not in {}'.format(limit_to_db, using))
        using = [limit_to_db]

    for db_alias in using:
        if model_class._meta.proxy:
            continue

        master_db = settings.DATABASES[db_alias].get('STANDBY', {}).get('MASTER')
        if not router.allow_migrate_model(master_db or db_alias, model_class):
            continue

        for builder in builders:
            yield model_class, builder.build(domain, model_class, db_alias)


def get_apps_and_models(app_or_model_label):
    """
    :param app_or_model_label: list of app labels ("app_label.model_name" or "app_label")
    :return: Tuple containing two sets: Set of AppConfigs, Set of model classes
    """
    specified_apps = set()
    specified_models = set()
    for label in app_or_model_label:
        if '.' in label:
            try:
                model = apps.get_model(label)
            except LookupError:
                raise DomainDumpError('Unknown model: %s' % label)
            specified_models.add(model)
        else:
            try:
                app_config = apps.get_app_config(label)
            except LookupError:
                from corehq.util.couch import get_document_class_by_doc_type
                from corehq.util.exceptions import DocumentClassNotFound

                # ignore this if it's a couch doc type
                try:
                    get_document_class_by_doc_type(label)
                except DocumentClassNotFound:
                    raise DomainDumpError('Unknown app in excludes: %s' % label)
            specified_apps.add(app_config)
    return specified_apps, specified_models


def _get_app_list(excluded_apps, included_apps):
    """
    :return: OrderedDict(app_config, model), ...)
    """
    app_list = OrderedDict()
    for label in APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP:
        app_config, model = get_model_class(label)
        if included_apps and app_config not in included_apps:
            continue
        if app_config in excluded_apps:
            continue

        app_list_value = app_list.setdefault(app_config, [])

        if model not in app_list_value:
            app_list_value.append(model)

    return app_list
