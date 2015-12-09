# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from corehq.apps.toggle_ui.migration_helpers import move_toggles


def migrate_formbuilder_commtrack_toggle(apps, schema_editor):
    move_toggles('transaction_question_types', 'commtrack')


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunPython(migrate_formbuilder_commtrack_toggle)
    ]
