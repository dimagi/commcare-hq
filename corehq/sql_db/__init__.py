from django.apps import AppConfig, apps
from django.conf import settings
from django.core.checks import Error, register, Tags
from django.db import DEFAULT_DB_ALIAS


class SQLDBAppConfig(AppConfig):
    name = 'corehq.sql_db'


default_app_config = 'corehq.sql_db.SQLDBAppConfig'


@register()
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
                Error('settings.{} should either be "default" for a default database'
                      'or a valid database defined in settings.DATABASES'.format(setting))
            )
    return errors


@register(Tags.database)
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
                    errors.append(Error(
                        '"settings.{}.{}" refers to multiple master databases. All READ database'
                        'must be refer to the same master database.'.format(setting_name, key)
                    ))
    return errors


@register(Tags.database, deploy=True)
def check_standby_databases(app_configs, **kwargs):
    from corehq.sql_db.util import get_standby_databases

    standbys = {
        db
        for db, config in settings.DATABASES
        if 'STANDBY' in config or 'HQ_ACCEPTABLE_STANDBY_DELAY' in config
    }
    confirmed_standbys = get_standby_databases()
    badly_configured = standbys - confirmed_standbys
    if badly_configured:
        return [
            Error("Some databases configured as STANDBY are not in recovery mode: {}".format(
                ', '.join(badly_configured)
            ))
        ]


@register(Tags.database, deploy=True)
def check_db_tables(app_configs, **kwargs):
    from corehq.sql_db.routers import ICDS_REPORTS_APP
    from corehq.sql_db.models import PartitionedModel
    from corehq.sql_db.util import get_db_aliases_for_partitioned_query

    errors = []

    # some apps only apply to specific envs
    env_specific_apps = {
        ICDS_REPORTS_APP: settings.ICDS_ENVS
    }

    def _check_model(model_class, using=None):
        try:
            model_class._default_manager.using(using).all().exists()
        except Exception as e:
            return Error('Error querying model on database "{}": "{}.{}": {}.{}({})'.format(
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

        if issubclass(model, PartitionedModel):
            for db in get_db_aliases_for_partitioned_query():
                error = _check_model(model, using=db)
                error and errors.append(error)
        else:
            error = _check_model(model)
            error and errors.append(error)
    return errors
