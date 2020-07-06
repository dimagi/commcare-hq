from collections import Counter, OrderedDict, defaultdict

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import router

from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from corehq.apps.dump_reload.sql.filters import (
    FilteredModelIteratorBuilder,
    SimpleFilter,
    UniqueFilteredModelIteratorBuilder,
    UserIDFilter,
    UsernameFilter
)
from corehq.apps.dump_reload.sql.serialization import JsonLinesSerializer
from corehq.apps.dump_reload.util import get_model_label, get_model_class
from corehq.sql_db.config import plproxy_config

APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP = defaultdict(list)
[APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP[iterator.model_label].append(iterator) for iterator in [
    FilteredModelIteratorBuilder('locations.LocationType', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('locations.SQLLocation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('blobs.BlobMeta', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.XFormInstanceSQL', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.XFormOperationSQL', SimpleFilter('form__domain')),
    FilteredModelIteratorBuilder('form_processor.CommCareCaseSQL', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.CommCareCaseIndexSQL', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.CaseAttachmentSQL', SimpleFilter('case__domain')),
    FilteredModelIteratorBuilder('form_processor.CaseTransaction', SimpleFilter('case__domain')),
    FilteredModelIteratorBuilder('form_processor.LedgerValue', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('form_processor.LedgerTransaction', SimpleFilter('case__domain')),
    FilteredModelIteratorBuilder('case_search.CaseSearchConfig', SimpleFilter('domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent', SimpleFilter('alertevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent', SimpleFilter('timedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent',
                                       SimpleFilter('randomtimedevent__schedule__domain')),
    UniqueFilteredModelIteratorBuilder('scheduling.SMSContent',
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
    FilteredModelIteratorBuilder('custom_data_fields.SQLCustomDataFieldsDefinition', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('custom_data_fields.SQLField', SimpleFilter('definition__domain')),
    FilteredModelIteratorBuilder('data_interfaces.AutomaticUpdateRule', SimpleFilter('domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.ClosedParentDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.CustomMatchDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.MatchPropertyDefinition',
                                       SimpleFilter('caserulecriteria__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.CustomActionDefinition',
                                       SimpleFilter('caseruleaction__rule__domain')),
    UniqueFilteredModelIteratorBuilder('data_interfaces.UpdateCaseDefinition',
                                       SimpleFilter('caseruleaction__rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CreateScheduleInstanceActionDefinition',
                                 SimpleFilter('caseruleaction__rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleAction', SimpleFilter('rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleCriteria', SimpleFilter('rule__domain')),
    FilteredModelIteratorBuilder('data_interfaces.CaseRuleSubmission', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_interfaces.DomainCaseRuleRun', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('auth.User', UsernameFilter()),
    FilteredModelIteratorBuilder('mobile_auth.SQLMobileAuthKeyRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.DeviceReportEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.ForceCloseEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.UserErrorEntry', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('phonelog.UserEntry', UserIDFilter('user_id')),
    FilteredModelIteratorBuilder('ota.DemoUserRestore', UserIDFilter('demo_user_id', include_web_users=False)),
    FilteredModelIteratorBuilder('domain_migration_flags.DomainMigrationProgress', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('products.SQLProduct', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('smsforms.SQLXFormsSession', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.MessagingEvent', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.MessagingSubEvent', SimpleFilter('parent__domain')),
    FilteredModelIteratorBuilder('sms.PhoneNumber', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SMS', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.Keyword', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.KeywordAction', SimpleFilter('keyword__domain')),
    FilteredModelIteratorBuilder('sms.QueuedSMS', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SelfRegistrationInvitation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SQLMobileBackend', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('sms.SQLMobileBackendMapping', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('cloudcare.ApplicationAccess', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('cloudcare.SQLAppGroup', SimpleFilter('application_access__domain')),
    FilteredModelIteratorBuilder('linked_domain.DomainLink', SimpleFilter('linked_domain')),
    FilteredModelIteratorBuilder('linked_domain.DomainLinkHistory', SimpleFilter('link__linked_domain')),
    FilteredModelIteratorBuilder('users.DomainPermissionsMirror', SimpleFilter('source')),
    FilteredModelIteratorBuilder('locations.LocationFixtureConfiguration', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('consumption.DefaultConsumption', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_dictionary.CaseType', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('data_dictionary.CaseProperty', SimpleFilter('case_type__domain')),
    FilteredModelIteratorBuilder('app_manager.GlobalAppConfig', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.AppReleaseByLocation', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('app_manager.LatestEnabledBuildProfiles', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadFileMeta', SimpleFilter('caseuploadrecord__domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadFormRecord', SimpleFilter('case_upload_record__domain')),
    FilteredModelIteratorBuilder('case_importer.CaseUploadRecord', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('translations.SMSTranslations', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('translations.TransifexBlacklist', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('translations.TransifexOrganization', SimpleFilter('transifexproject__domain')),
    FilteredModelIteratorBuilder('translations.TransifexProject', SimpleFilter('domain')),
    FilteredModelIteratorBuilder('zapier.ZapierSubscription', SimpleFilter('domain')),
]]


class SqlDataDumper(DataDumper):
    slug = 'sql'

    def dump(self, output_stream):
        stats = Counter()
        objects = get_objects_to_dump(self.domain, self.excludes, stats_counter=stats, stdout=self.stdout)
        JsonLinesSerializer().serialize(
            objects,
            use_natural_foreign_keys=False,
            use_natural_primary_keys=True,
            stream=output_stream
        )
        return stats


def get_objects_to_dump(domain, excludes, stats_counter=None, stdout=None):
    """
    :param domain: domain name to filter with
    :param app_list: List of (app_config, model_class) tuples to dump
    :param excluded_models: List of model_class classes to exclude
    :return: generator yielding models objects
    """
    if stats_counter is None:
        stats_counter = Counter()
    for model_class, builder in get_model_iterator_builders_to_dump(domain, excludes):
        model_label = get_model_label(model_class)
        for iterator in builder.iterators():
            for obj in iterator:
                stats_counter.update([model_label])
                yield obj
        if stdout:
            stdout.write('Dumped {} {}\n'.format(stats_counter[model_label], model_label))


def get_model_iterator_builders_to_dump(domain, excludes):
    """
    :param domain: domain name to filter with
    :param app_list: List of (app_config, model_class) tuples to dump
    :param excluded_models: List of model_class classes to exclude
    :return: generator yielding query sets
    """
    excluded_apps, excluded_models = get_excluded_apps_and_models(excludes)
    app_config_models = _get_app_list(excluded_apps)

    # Collate the objects to be serialized.
    for model_class in serializers.sort_dependencies(list(app_config_models.items())):
        if model_class in excluded_models:
            continue

        for model_class, builder in get_all_model_iterators_builders_for_domain(model_class, domain):
            yield model_class, builder


def get_all_model_iterators_builders_for_domain(model_class, domain, limit_to_db=None):
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
        if not model_class._meta.proxy and router.allow_migrate_model(db_alias, model_class):
            iterator_builders = APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP[get_model_label(model_class)]
            for builder in iterator_builders:
                yield model_class, builder.build(domain, model_class, db_alias)


def get_excluded_apps_and_models(excludes):
    """
    :param excludes: list of app labels ("app_label.model_name" or "app_label") to exclude
    :return: Tuple containing two sets: Set of AppConfigs to exclude, Set of model classes to excluded.
    """
    excluded_apps = set()
    excluded_models = set()
    for exclude in excludes:
        if '.' in exclude:
            try:
                model = apps.get_model(exclude)
            except LookupError:
                raise DomainDumpError('Unknown model in excludes: %s' % exclude)
            excluded_models.add(model)
        else:
            try:
                app_config = apps.get_app_config(exclude)
            except LookupError:
                raise DomainDumpError('Unknown app in excludes: %s' % exclude)
            excluded_apps.add(app_config)
    return excluded_apps, excluded_models


def _get_app_list(excluded_apps):
    """
    :return: OrderedDict(app_config, model), ...)
    """
    app_list = OrderedDict()
    for label in APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP:
        app_config, model = get_model_class(label)
        if app_config in excluded_apps:
            continue

        app_list_value = app_list.setdefault(app_config, [])

        if model not in app_list_value:
            app_list_value.append(model)

    return app_list
