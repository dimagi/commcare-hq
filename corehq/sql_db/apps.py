from __future__ import absolute_import

from django.apps import AppConfig
from django.conf import settings
from django.db import connections
from memoized import memoized


class SqlDbAppConfig(AppConfig):
    name = 'corehq.sql_db'

    def ready(self):
        """This gets run when Django starts"""
        identify_standby_databases()


# gets written when `identify_standby_databases` gets called or
#   after Django starts.
STANDBY_DATABASE_ALIASES = []

@memoized
def identify_standby_databases():
    for db_alias in settings.DATABASES:
        with connections[db_alias].cursor() as cursor:
            cursor.execute("SELECT pg_is_in_recovery()")
            [(is_standby, )] = cursor.fetchall()
            if is_standby:
                STANDBY_DATABASE_ALIASES.append(db_alias)
