# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.db import DEFAULT_ENGINE_ID
from corehq.util.couch import IterDB
from dimagi.utils.couch.database import iter_docs


def set_default_engine_ids(apps, schema_editor):
    ucr_db = DataSourceConfiguration.get_db()
    with IterDB(ucr_db) as iter_db:
        for doc in iter_docs(ucr_db, DataSourceConfiguration.all_ids()):
            if not doc.get('engine_id'):
                doc['engine_id'] = DEFAULT_ENGINE_ID
                iter_db.save(doc)


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.RunPython(set_default_engine_ids),
    ]
