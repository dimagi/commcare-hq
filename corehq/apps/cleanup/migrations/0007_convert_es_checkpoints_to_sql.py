# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.cleanup.pillow_migrations import migrate_legacy_pillows, noop_reverse_migration


def migrate_es_pillows(apps, schema_editor):
    pillow_names = [
        'AppPillow',
        'CasePillow',
        'DomainPillow',
        'GroupPillow',
        'SMSPillow',
        'UserPillow',
        'XFormPillow',
        # 'corehq.pillows.user.GroupToUserPillow',
        # 'corehq.pillows.user.UnknownUsersPillow',
        # 'corehq.pillows.sofabed.FormDataPillow',
        # 'corehq.pillows.sofabed.CaseDataPillow',
    ]
    migrate_legacy_pillows(apps, pillow_names)


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0006_convert_report_es_checkpoints_to_sql'),
    ]

    operations = [
        migrations.RunPython(migrate_es_pillows, noop_reverse_migration)
    ]
