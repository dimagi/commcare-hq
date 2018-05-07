# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function

from __future__ import absolute_import
from django.conf import settings
from django.db import models, migrations
from corehq.sql_db.operations import HqRunPython


RENAMES = (
    ("applications-to-elasticsearch", "ApplicationToElasticsearchPillow-hqapps_2016-10-20_1835"),
    ("all-cases-to-elasticsearch", "CaseToElasticsearchPillow-hqcases_2016-03-04"),
    ("all-xforms-to-elasticsearch", "XFormToElasticsearchPillow-xforms_2016-07-07"),
    ("case-search-to-elasticsearch", "CaseSearchToElasticsearchPillow-case_search_2018-04-27"),
    ("GroupPillow", "GroupPillow-hqgroups_20150403_1501"),
    ("GroupToUserPillow", "GroupToUserPillow-hqusers_2016-09-29"),
    ("KafkaDomainPillow", "KafkaDomainPillow-hqdomains_2016-08-08"),
    ("ledger-to-elasticsearch", "LedgerToElasticsearchPillow-ledgers_2016-03-15"),
    ("report-cases-to-elasticsearch", "ReportCaseToElasticsearchPillow-report_cases_czei39du507m9mmpqk3y01x72a3ux4p0"),
    ("report-xforms-to-elasticsearch", "ReportXFormToElasticsearchPillow-report_xforms_20160707_2322"),
    ("sql-sms-to-es", "SqlSMSPillow-smslogs_708c77f8e5fe00286fa5791e9fa7d45f"),
    ("UnknownUsersPillow", "UnknownUsersPillow-hqusers_2016-09-29"),
    ("UserPillow", "UserPillow-hqusers_2016-09-29"),
)


def copy_checkpoints(apps, schema_editor):
    from pillowtop import get_all_pillow_instances
    DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
    current_checkoint_ids = set(
        [pillow_instance.checkpoint.checkpoint_id for pillow_instance in get_all_pillow_instances()]
    )

    for old_id, new_id in RENAMES:
        try:
            checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id=old_id)
            # since checkpoint_id is the primary key, this should make a new model
            # which is good in case we need to rollback
            checkpoint.checkpoint_id = new_id
            checkpoint.save()
        except DjangoPillowCheckpoint.DoesNotExist:
            if not settings.UNIT_TESTING:
                print('warning: legacy pillow checkpoint with ID {} not found'.format(old_id))
        if new_id not in current_checkoint_ids and not settings.UNIT_TESTING:
            print('warning: no current pillow found with checkpoint ID {}'.format(new_id))


def delete_checkpoints(apps, schema_editor):
    DjangoPillowCheckpoint = apps.get_model('pillowtop', 'DjangoPillowCheckpoint')
    for _, new_id in RENAMES:
        try:
            checkpoint = DjangoPillowCheckpoint.objects.get(checkpoint_id=new_id)
            checkpoint.delete()
        except DjangoPillowCheckpoint.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0011_merge_couch_sql_pillows'),
        ('pillowtop', '0003_auto_20170411_1957'),
    ]

    operations = [
        HqRunPython(copy_checkpoints, delete_checkpoints)
    ]
