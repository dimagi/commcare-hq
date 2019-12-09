from django.apps import AppConfig


class SqlDbAppConfig(AppConfig):
    name = 'corehq.sql_db'

    def ready(self):
        from corehq.sql_db import (
            check_db_tables,
            check_standby_configs,
            check_standby_databases,
            custom_db_checks
        )
