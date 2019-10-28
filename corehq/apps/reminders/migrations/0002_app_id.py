from django.db import migrations

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.reminders.models import SurveyKeyword
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar

app_id_by_form_unique_id = {}


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    doc_ids = get_doc_ids_by_class(SurveyKeyword) + get_deleted_doc_ids_by_class(SurveyKeyword)
    iter_update(SurveyKeyword.get_db(), _add_field, with_progress_bar(doc_ids))


def _add_field(doc):
    if doc.get('form_unique_id', None):
        form_unique_id = doc['form_unique_id']
        if form_unique_id not in app_id_by_form_unique_id:
            apps = get_apps_in_domain(doc['domain'])
            for app in apps:
                for module in app.modules:
                    for form in module.get_forms():
                        app_id_by_form_unique_id[form.unique_id] = app.get_id
        doc['app_id'] = app_id_by_form_unique_id.get(form_unique_id, None)
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
