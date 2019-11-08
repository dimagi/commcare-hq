from django.db import migrations

from corehq.apps.app_manager.util import get_app_id_from_form_unique_id
from corehq.apps.reminders.models import SurveyKeyword
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    doc_ids = get_doc_ids_by_class(SurveyKeyword) + get_deleted_doc_ids_by_class(SurveyKeyword)
    iter_update(SurveyKeyword.get_db(), _add_field, with_progress_bar(doc_ids))


def _add_field(doc):
    if doc.get('form_unique_id', None) and not doc.get('app_id', None):
        doc['app_id'] = get_app_id_from_form_unique_id(doc['domain'], doc['form_unique_id'])
        if doc['app_id']:
            return DocUpdate(doc)


class Migration(migrations.Migration):

    dependencies = [
        ('reminders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_populate_app_id,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
