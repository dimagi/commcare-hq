from pathlib import Path

from django.conf import settings
from django.db import migrations

import sqlalchemy

from corehq.apps.project_db.table_ddl import get_project_db_engine
from corehq.sql_db.connections import PROJECT_DB_ENGINE_ID, connection_manager

SETUP_SQL_PATH = Path(__file__).parent.parent / 'project_db_setup.sql'
LIB_SQL_PATH = Path(__file__).parent.parent / 'lib_projectdb.sql'


def _setup(apps, schema_editor):
    if not connection_manager.engine_id_is_available(PROJECT_DB_ENGINE_ID):
        return
    with get_project_db_engine().begin() as conn:
        if settings.DEBUG or settings.UNIT_TESTING:
            # Production applies this via commcare-cloud because HQ doesn't
            # have sufficient DB permissions
            conn.execute(sqlalchemy.text(SETUP_SQL_PATH.read_text()))
        conn.execute(sqlalchemy.text(LIB_SQL_PATH.read_text()))


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunPython(_setup, migrations.RunPython.noop),
    ]
