from django.db import migrations
from corehq.apps.domain.models import Domain
from corehq.dbaccessors.couchapps.all_docs import (
    get_doc_ids_by_class,
    get_deleted_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _remove_usercase_enabled(apps, schema_editor):
    ids = get_doc_ids_by_class(Domain) + get_deleted_doc_ids_by_class(Domain)
    iter_update(Domain.get_db(), _pop_field, with_progress_bar(ids), chunksize=1)


def _pop_field(doc):
    if 'usercase_enabled' in doc:
        doc.pop('usercase_enabled')
        return DocUpdate(doc)


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0018_enable_all_add_ons'),
    ]

    operations = [
        migrations.RunPython(
            _remove_usercase_enabled,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
