# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
from django.core.management import call_command

from dimagi.utils.couch import sync_docs

import corehq.apps.app_manager.models.common as models_common
import corehq.apps.app_manager.models.schedules as models_schedules

def sync_app_manager_docs(apps, schema_editor):
    sync_docs.sync(models_common, verbosity=2)
    sync_docs.sync(models_schedules, verbosity=2)


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.RunPython(sync_app_manager_docs),
    ]
