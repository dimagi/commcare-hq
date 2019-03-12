# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.apps import apps
from django.db import connections, migrations
from django.conf import settings

from corehq.sql_db.connections import get_icds_ucr_db_alias


def _citus_composite_key_sql(model_cls):
    connection = connections[get_icds_ucr_db_alias()]
    with connection.schema_editor() as schema_editor:
        pkey_name = '{}_pkey'.format(model_cls._meta.db_table)
        fields = list(model_cls._meta.unique_together)[0]
        columns = [model_cls._meta.get_field(field).column for field in fields]
        index = schema_editor._create_index_name(model_cls, columns, suffix="_uniq")
        sql = """
            CREATE UNIQUE INDEX {index} on "{table}" ({cols});
            ALTER TABLE "{table}" DROP CONSTRAINT {pkey_name},
            ADD CONSTRAINT {pkey_name} PRIMARY KEY USING INDEX {index};
        """.format(
            table=model_cls._meta.db_table,
            pkey_name=pkey_name,
            index=index,
            cols=','.join(columns)
        )
        reverse_sql = """
            ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS {index},
            DROP CONSTRAINT IF EXISTS {pkey_name},
            ADD CONSTRAINT {pkey_name} PRIMARY KEY ({pkey});
            DROP INDEX IF EXISTS {index};
        """.format(
            table=model_cls._meta.db_table,
            pkey_name=pkey_name,
            pkey=model_cls._meta.pk.name,
            index=index,
        )
    if not getattr(settings, 'IS_ON_CITUSDB_BACKEND', False):
        print "Not CITUS"
        return migrations.RunSQL.noop, reverse_sql
    else:
        print "Yes CITUS"
        print sql
        return sql, reverse_sql


def get_sql_operations():
    models_to_update = [
        'aggregatebirthpreparednesforms',
        'aggregateccsrecorddeliveryforms',
        'aggregateccsrecordpostnatalcareforms',
        'aggregateccsrecordthrforms',
        'aggregatechildhealthdailyfeedingforms',
        'aggregatechildhealthpostnatalcareforms',
        'aggregatechildhealththrforms',
        'aggregatecomplementaryfeedingforms',
        'aggregategrowthmonitoringforms',
        'dailyattendance',
    ]

    operations = []
    for model_name in models_to_update:
        model = apps.get_model('icds_reports', model_name)
        sql, reverse_sql = _citus_composite_key_sql(model)
        operations.append(migrations.RunSQL(
            sql,
            reverse_sql=reverse_sql,
            state_operations=[migrations.AlterUniqueTogether(
                name=model_name,
                unique_together=set(model._meta.unique_together),
            )]
        ))
    return operations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0103_aggregateccsrecordcomplementaryfeedingforms_supervisor_id'),
    ]

    operations = get_sql_operations()
