from collections import OrderedDict, Counter

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import router

from corehq.apps.dump_reload.exceptions import DomainDumpError
from corehq.apps.dump_reload.interface import DataDumper
from corehq.apps.dump_reload.sql.filters import SimpleFilter, UsernameFilter, UserIDFilter
from corehq.apps.dump_reload.sql.serialization import JsonLinesSerializer
from corehq.apps.dump_reload.util import get_model_label
from corehq.sql_db.config import partition_config
from corehq.util.decorators import ContextDecorator

# order is important here for foreign key constraints
APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP = OrderedDict([
    ('locations.LocationType', SimpleFilter('domain')),
    ('locations.SQLLocation', SimpleFilter('domain')),
    ('form_processor.XFormInstanceSQL', SimpleFilter('domain')),
    ('form_processor.XFormAttachmentSQL', SimpleFilter('form__domain')),
    ('form_processor.XFormOperationSQL', SimpleFilter('form__domain')),
    ('form_processor.CommCareCaseSQL', SimpleFilter('domain')),
    ('form_processor.CommCareCaseIndexSQL', SimpleFilter('domain')),
    ('form_processor.CaseAttachmentSQL', SimpleFilter('case__domain')),
    ('form_processor.CaseTransaction', SimpleFilter('case__domain')),
    ('form_processor.LedgerValue', SimpleFilter('domain')),
    ('form_processor.LedgerTransaction', SimpleFilter('case__domain')),
    ('case_search.CaseSearchConfig', SimpleFilter('domain')),
    ('data_interfaces.AutomaticUpdateRule', SimpleFilter('domain')),
    ('data_interfaces.AutomaticUpdateRuleCriteria', SimpleFilter('rule__domain')),
    ('data_interfaces.AutomaticUpdateAction', SimpleFilter('rule__domain')),
    ('auth.User', UsernameFilter()),
    ('phonelog.DeviceReportEntry', SimpleFilter('domain')),
    ('phonelog.ForceCloseEntry', SimpleFilter('domain')),
    ('phonelog.UserErrorEntry', SimpleFilter('domain')),
    ('phonelog.UserEntry', UserIDFilter('user_id')),
    ('ota.DemoUserRestore', UserIDFilter('demo_user_id', include_web_users=False)),
    ('domain_migration_flags.DomainMigrationProgress', SimpleFilter('domain')),
    ('products.SQLProduct', SimpleFilter('domain')),
    ('sms.MessagingEvent', SimpleFilter('domain')),
    ('sms.MessagingSubEvent', SimpleFilter('parent__domain')),
    ('sms.PhoneNumber', SimpleFilter('domain')),
])


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
    for model_class, query in get_querysets_to_dump(domain, excludes):
        model_label = get_model_label(model_class)
        for obj in query.iterator():
            stats_counter.update([model_label])
            yield obj
        if stdout:
            stdout.write('Dumped {} {}\n'.format(stats_counter[model_label], model_label))


def get_querysets_to_dump(domain, excludes):
    """
    :param domain: domain name to filter with
    :param app_list: List of (app_config, model_class) tuples to dump
    :param excluded_models: List of model_class classes to exclude
    :return: generator yielding query sets
    """
    excluded_apps, excluded_models = get_excluded_apps_and_models(excludes)
    app_config_models = _get_app_list(excluded_apps)

    # Collate the objects to be serialized.
    for model_class in serializers.sort_dependencies(app_config_models.items()):
        if model_class in excluded_models:
            continue

        for model_class, queryset in get_all_model_querysets_for_domain(model_class, domain):
            yield model_class, queryset


def get_all_model_querysets_for_domain(model_class, domain):
    using = router.db_for_read(model_class)
    if settings.USE_PARTITIONED_DATABASE and using == partition_config.get_proxy_db():
        using = partition_config.get_form_processing_dbs()
    else:
        using = [using]

    for db_alias in using:
        if not model_class._meta.proxy and router.allow_migrate_model(db_alias, model_class):
            objects = model_class._default_manager

            queryset = objects.using(db_alias).order_by(model_class._meta.pk.name)

            filters = get_model_domain_filters(model_class, domain)
            for filter in filters:
                yield model_class, queryset.filter(filter)


def get_model_domain_filters(model_class, domain):
    label = get_model_label(model_class)
    filter = APP_LABELS_WITH_FILTER_KWARGS_TO_DUMP[label]
    return filter.get_filters(domain)


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
        app_label, model_label = label.split('.')
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise DomainDumpError("Unknown application: %s" % app_label)
        if app_config in excluded_apps:
            continue
        try:
            model = app_config.get_model(model_label)
        except LookupError:
            raise DomainDumpError("Unknown model: %s.%s" % (app_label, model_label))

        app_list_value = app_list.setdefault(app_config, [])

        if model not in app_list_value:
            app_list_value.append(model)

    return app_list
