from django.apps import apps
from django.conf import settings
from django.core import checks
from django.db import DEFAULT_DB_ALIAS

from corehq.sql_db.exceptions import PartitionValidationError


@checks.register('settings')
def custom_db_checks(app_configs, **kwargs):
    errors = []
    custom_db_settings = [
        'SYNCLOGS_SQL_DB_ALIAS'
    ]
    for setting in custom_db_settings:
        default = getattr(settings, setting) == DEFAULT_DB_ALIAS
        custom = not default and getattr(settings, setting) in settings.DATABASES
        if not (default or custom):
            errors.append(
                checks.Error('settings.{} should either be "default" for a default database'
                      'or a valid database defined in settings.DATABASES'.format(setting))
            )
    return errors


@checks.register('settings')
def check_plproxy_config(app_configs, **kwargs):
    allowed_keys = {'PROXY_FOR_STANDBYS', 'PROXY', 'SHARDS', 'PLPROXY_HOST'}
    messages = []
    for db, config in settings.DATABASES.items():
        if 'PLPROXY' in config:
            unknown_keys = set(config['PLPROXY']) - allowed_keys
            if unknown_keys:
                messages.append(checks.Warning(
                    f'Unrecognised PLPROXY settings: {unknown_keys}'
                ))

    try:
        from corehq.sql_db.config import plproxy_config, _get_standby_plproxy_config
        if plproxy_config:
            _get_standby_plproxy_config(plproxy_config)
    except PartitionValidationError as e:
        messages.append(checks.Error(f'Error in PLPROXY standby configuration: {e}'))
    return messages


@checks.register('settings')
def check_standby_configs(app_configs, **kwargs):
    standby_to_master = {
        db: config.get('STANDBY', {}).get('MASTER')
        for db, config in settings.DATABASES.items()
        if config.get('STANDBY', {}).get('MASTER')
    }
    all_masters = {
        db for db, config in settings.DATABASES.items()
        if 'STANDBY' not in config and 'HQ_ACCEPTABLE_STANDBY_DELAY' not in config
    }

    errors = []
    custom_db_settings = [
        'REPORTING_DATABASES',
        'LOAD_BALANCED_APPS'
    ]
    for setting_name in custom_db_settings:
        setting = getattr(settings, setting_name)
        if not setting:
            continue
        for key, config in setting.items():
            if 'READ' in config:
                read_dbs = {db for db, weight in config['READ']}
                masters = read_dbs & all_masters
                standby_masters = {
                    standby_to_master[db]
                    for db in read_dbs
                    if db in standby_to_master
                }
                if len(masters | standby_masters) > 1:
                    errors.append(checks.Error(
                        '"settings.{}.{}" refers to multiple master databases. All READ database'
                        'must be refer to the same master database.'.format(setting_name, key)
                    ))
    return errors


@checks.register(checks.Tags.database, deploy=True)
def check_standby_databases(app_configs, **kwargs):
    from corehq.sql_db.util import get_standby_databases

    standbys = {
        db
        for db, config in settings.DATABASES.items()
        if 'STANDBY' in config or 'HQ_ACCEPTABLE_STANDBY_DELAY' in config
    }
    confirmed_standbys = get_standby_databases()
    badly_configured = standbys - confirmed_standbys
    if badly_configured:
        return [
            checks.Error("Some databases configured as STANDBY are not in recovery mode: {}".format(
                ', '.join(badly_configured)
            ))
        ]
    return []


@checks.register(checks.Tags.database, deploy=True)
def check_db_tables(app_configs, **kwargs):
    from corehq.sql_db.models import PartitionedModel
    from corehq.sql_db.util import get_db_aliases_for_partitioned_query

    errors = []

    # some apps only apply to specific envs
    env_specific_apps = {
        'icds_reports': settings.ICDS_ENVS,
        'aaa': ('none',),
    }

    ignored_models = [
        'DeprecatedXFormAttachmentSQL'
    ]

    def _check_model(model_class, using=None):
        try:
            model_class._default_manager.using(using).all().exists()
        except Exception as e:
            return checks.Error('checks.Error querying model on database "{}": "{}.{}": {}.{}({})'.format(
                using or DEFAULT_DB_ALIAS,
                model_class._meta.app_label, model_class.__name__,
                e.__class__.__module__, e.__class__.__name__,
                e
            ))

    for model in apps.get_models():
        app_label = model._meta.app_label
        enabled_envs = env_specific_apps.get(app_label)
        if enabled_envs and settings.SERVER_ENVIRONMENT not in enabled_envs:
            continue

        if model.__name__ in ignored_models or not model._meta.managed:
            continue

        if issubclass(model, PartitionedModel):
            for db in get_db_aliases_for_partitioned_query():
                checks.Error = _check_model(model, using=db)
                checks.Error and errors.append(checks.Error)
        else:
            checks.Error = _check_model(model)
            checks.Error and errors.append(checks.Error)
    return errors
