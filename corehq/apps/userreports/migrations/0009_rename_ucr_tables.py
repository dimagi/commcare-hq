# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import sys
from collections import defaultdict

from django.db import migrations

from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_table_name, LEGACY_UCR_TABLE_PREFIX
from corehq.sql_db.connections import connection_manager
from corehq.util.django_migrations import skip_on_fresh_install

GIT_COMMIT_WITH_MANAGEMENT_COMMAND = "8ec458ce9dd6a690c0b48bba07ffee2455f267d2"
AUTO_MIGRATE_FAILED_MESSAGE = """
A migration must be performed before this environment can be upgraded to the
latest version of CommCareHQ. To perform the migration you will need to do the following:

* Checkout an older version of CommCareHQ:

    git checkout {commit}

* Stop all UCR pillow processes

* Run the following management commands:

    python manage.py rename_ucr_tables create-views --verbose --execute --noconfirm

    python manage.py rename_ucr_tables rename-tables --verbose --execute --noconfirm


""".format(commit=GIT_COMMIT_WITH_MANAGEMENT_COMMAND)


def table_exists(connection, table_name):
    res = connection.execute("select 1 from pg_tables where tablename = %s", table_name)
    return bool(list(res))


def get_legacy_table_name(data_source):
    return get_table_name(
        data_source.domain, data_source.table_id, max_length=63, prefix=LEGACY_UCR_TABLE_PREFIX
    )


def _data_sources_by_engine_id():
    by_engine_id = defaultdict(list)
    for ds in StaticDataSourceConfiguration.all():
        ds_engine_id = ds['engine_id']
        by_engine_id[ds_engine_id].append(ds)

    for ds in DataSourceConfiguration.all():
        ds_engine_id = ds['engine_id']
        by_engine_id[ds_engine_id].append(ds)

    return by_engine_id


@skip_on_fresh_install
def _assert_migrated(apps, schema_editor):
    for engine_id, data_sources in _data_sources_by_engine_id().items():
        with connection_manager.get_engine(engine_id).begin() as conn:
            for data_source in data_sources:
                legacy_table_name = get_legacy_table_name(data_source)
                new_table_name = get_table_name(data_source.domain, data_source.table_id)
                if (
                    table_exists(conn, legacy_table_name)
                    and not table_exists(conn, new_table_name)
                ):
                    print("")
                    print(AUTO_MIGRATE_FAILED_MESSAGE)
                    sys.exit(1)


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0008_new_table_name_views'),
    ]

    operations = [
        migrations.RunPython(_assert_migrated, migrations.RunPython.noop, elidable=True)
    ]
