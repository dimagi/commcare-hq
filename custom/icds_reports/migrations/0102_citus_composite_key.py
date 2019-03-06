# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import migrations
from django.conf import settings
from corehq.sql_db.operations import HqRunPython


def _citus_composite_key_migration(apps, schema_editor):
    models_to_update = [
        'aggregateawcinfrastructureforms',
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
        'awwincentivereport'
    ]
    if not getattr(settings, 'IS_ON_CITUSDB_BACKEND', False):
        return
    else:
        with schema_editor.connection.cursor() as cursor:
            for model in models_to_update:
                model_cls = apps.get_model('icds_reports', model)
                pkey = '{}_pkey'.format(model_cls._meta.db_table)
                fields = list(model_cls._meta.unique_together)[0]
                columns = [model_cls._meta.get_field(field).column for field in fields]
                index = schema_editor._create_index_name(model_cls, columns, suffix="_uniq")
                cursor.execute("""
                    CREATE UNIQUE INDEX {index} on "{table}" ({cols});
                    ALTER TABLE "{table}" DROP CONSTRAINT {pkey},
                    ADD CONSTRAINT {pkey} PRIMARY KEY USING INDEX {index};
                """.format(
                    table=model_cls._meta.db_table,
                    pkey=pkey,
                    index=index,
                    cols=','.join(columns)
                ))


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_squashed_0052_ensure_report_builder_plans'),
    ]

    operations = [
        HqRunPython(_citus_composite_key_migration),
    ]
