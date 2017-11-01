# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.migrations.operations.special import RunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0003_auto_20170411_1957'),
    ]

    operations = [
        # in case there's a rollback we want to override any existing value
        RunSQL("DELETE FROM pillowtop_djangopillowcheckpoint WHERE checkpoint_id = 'synclogs'"),
        RunSQL("""
            INSERT INTO pillowtop_djangopillowcheckpoint
            (checkpoint_id, sequence, "timestamp", old_sequence, sequence_format)
            SELECT 'synclogs', sequence, "timestamp", old_sequence, sequence_format
            FROM pillowtop_djangopillowcheckpoint WHERE checkpoint_id = 'synclog'
        """)
    ]
