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
def _pop_deprecated_field(apps, schema_editor):
    app_ids = (get_doc_ids_by_class(LinkedApplication)
               + get_deleted_doc_ids_by_class(LinkedApplication))
    iter_update(LinkedApplication.get_db(), _pop_field, with_progress_bar(app_ids), chunksize=1)


def _pop_field(app_doc):
    if 'uses_master_app_form_ids' in app_doc:
        app_doc.pop('uses_master_app_form_ids')
        return DocUpdate(app_doc)


def _reverse_noop(app, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0007_add_linked_app_fields_to_es'),
    ]

    operations = [
        migrations.RunPython(_pop_deprecated_field,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
