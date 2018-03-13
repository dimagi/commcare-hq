from __future__ import absolute_import
from django.apps import AppConfig
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
        custom =  not default and getattr(settings, setting) in settings.DATABASES
        if not (default or custom):
            errors.append(
                Error('settings.{} should either be "default" for a default database'
                      'or a valid database defined in settings.DATABASES'.format(setting))
            )
        if custom and not settings.USE_PARTITIONED_DATABASE:
            errors.append(
                Error('A custom database can\'tbe used without a partitioned database.'
                      'settings.USE_PARTITIONED_DATABASE must be True if '
                      'settings.{} is set to a custom database.'.format(setting))
            )
    return errors


@register(Tags.database, deploy=True)
def check_db_tables(app_configs, **kwargs):
    errors = []
    from django.apps import apps
    from corehq.sql_db.models import PartitionedModel
    from corehq.sql_db.util import get_db_aliases_for_partitioned_query

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
        if issubclass(model, PartitionedModel):
            for db in get_db_aliases_for_partitioned_query():
                error = _check_model(model, using=db)
                error and errors.append(error)
        else:
            error = _check_model(model)
            error and errors.append(error)
    return errors
