from __future__ import absolute_import, unicode_literals

from django.conf import settings

citus_masters = [name for name, db in settings.DATABASES.items() if db.get('ROLE') == 'citus_master']
assert len(citus_masters) in (0, 1), "Multiple CitusDB masters found"
CITUS_MASTER = citus_masters[0] if citus_masters else None

CITUS_WORKERS = [name for name, db in settings.DATABASES.items() if db.get('ROLE') == 'citus_worker']
if CITUS_MASTER:
    assert CITUS_WORKERS, "No CitusDB workers found"


class CitusDBRouter(object):
    def allow_migrate(self, db, app_label, model=None, **hints):
        if app_label == 'citus_master':
            return db == CITUS_MASTER
        elif app_label == 'citus_worker':
            return db in CITUS_WORKERS
