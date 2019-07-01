from __future__ import absolute_import, unicode_literals

from django.db import migrations

from corehq.apps.app_manager.models import LinkedApplication
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _populate_linked_app_fields(apps, schema_editor):
    app_ids = (get_doc_ids_by_class(LinkedApplication)
               + get_deleted_doc_ids_by_class(LinkedApplication))
    iter_update(LinkedApplication.get_db(), _add_fields, with_progress_bar(app_ids))


def _add_fields(app_doc):
    app_doc['progenitor_app_id'] = app_doc['master']
    app_doc['upstream_app_id'] = app_doc['master']
    app_doc['upstream_version'] = app_doc['version']
    return DocUpdate(app_doc)


def _reverse_noop(app, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0003_auto_20190326_0853'),
    ]

    operations = [
        migrations.RunPython(_populate_linked_app_fields,
                             reverse_code=migrations.RunPython.noop),
    ]
