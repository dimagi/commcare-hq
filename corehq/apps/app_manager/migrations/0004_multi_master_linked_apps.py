from __future__ import absolute_import, unicode_literals

from django.db import migrations

from corehq.apps.app_manager.models import LinkedApplication
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0003_auto_20190326_0853'),
    ]

    operations = [
        migrations.RunPython(_populate_linked_app_fields, reverse_code=_reverse_noop),
    ]


def _populate_linked_app_fields(apps, schema_editor):
    app_ids = get_doc_ids_by_class(LinkedApplication)
    iter_update(LinkedApplication.get_db(), add_fields, app_ids)


def add_fields(app_doc):
    app_doc['progenitor_id'] = app_doc['master']
    app_doc['pulled_from_master_app_id'] = app_doc['master']
    app_doc['pulled_from_master_version'] = app_doc['version']
    return DocUpdate(app_doc)


def _reverse_noop(app, schema_editor):
    pass
