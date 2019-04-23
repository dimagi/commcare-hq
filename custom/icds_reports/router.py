from __future__ import absolute_import, unicode_literals

from corehq.sql_db.connections import connection_manager
from custom.icds_reports.const import ICDS_UCR_ENGINE_ID

ICDS_REPORTS_APP = 'icds_reports'


class ICDSReportsRouter(object):

    def db_for_read(self, model, **hints):
        return db_for_read_write(model, write=False)

    def db_for_write(self, model, **hints):
        return db_for_read_write(model, write=True)

    def allow_migrate(self, db, app_label, model=None, **hints):
        is_icds_app = (app_label == ICDS_REPORTS_APP)
        if not is_icds_app:
            # defer to other routers
            return None

        return db == get_icds_ucr_db_alias()

    def allow_relation(self, obj1, obj2, **hints):
        app1, app2 = obj1._meta.app_label, obj2._meta.app_label
        if app1 == ICDS_REPORTS_APP or app2 == ICDS_REPORTS_APP:
            return app1 == app2
        return None


def db_for_read_write(model, write=True):
    """
    :param model: Django model being queried
    :param write: Default to True since the DB for writes can also handle reads
    :return: Django DB alias to use for query
    """
    app_label = model._meta.app_label

    if app_label == ICDS_REPORTS_APP:
        engine_id = ICDS_UCR_ENGINE_ID
        if not write:
            engine_id = connection_manager.get_load_balanced_read_db_alias(ICDS_UCR_ENGINE_ID)
        return connection_manager.get_django_db_alias(engine_id)


def get_icds_ucr_db_alias():
    try:
        return connection_manager.get_django_db_alias(ICDS_UCR_ENGINE_ID)
    except KeyError:
        return None
