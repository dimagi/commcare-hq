from __future__ import absolute_import
from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register


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
