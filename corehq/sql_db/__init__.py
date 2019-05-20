from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig, apps
from django.conf import settings
from django.core.checks import Error, register, Tags


class SQLDBAppConfig(AppConfig):
    name = 'corehq.sql_db'


default_app_config = 'corehq.sql_db.SQLDBAppConfig'


@register()
def custom_db_checks(app_configs, **kwargs):
    errors = []
    custom_db_settings = [
        'WAREHOUSE_DATABASE_ALIAS',
        'SYNCLOGS_SQL_DB_ALIAS'
    ]
    for setting in custom_db_settings:
        default = getattr(settings, setting) == 'default'
        custom = not default and getattr(settings, setting) in settings.DATABASES
        if not (default or custom):
            errors.append(
                Error('settings.{} should either be "default" for a default database'
                      'or a valid database defined in settings.DATABASES'.format(setting))
            )
    return errors


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

    skip = (
        'warehouse',  # remove this once the warehouse tables are created
    )

    def _check_model(model_class, using=None):
        try:
            model_class._default_manager.using(using).all().exists()
        except Exception as e:
            return Error('Error querying model on database "{}": "{}.{}": {}.{}({})'.format(
                using or 'default',
                model_class._meta.app_label, model_class.__name__,
                e.__class__.__module__, e.__class__.__name__,
                e
            ))

    for model in apps.get_models():
        app_label = model._meta.app_label
        if app_label in skip:
            continue

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
