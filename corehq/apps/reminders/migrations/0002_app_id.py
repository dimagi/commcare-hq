from django.db import migrations

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.dbaccessors.couchapps.all_docs import (
    get_deleted_doc_ids_by_class,
    get_doc_ids_by_class,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _populate_app_id(apps, schema_editor):
    SurveyKeyword = apps.get_model('reminders', 'SurveyKeyword')
    doc_ids = get_doc_ids_by_class(SurveyKeyword) + get_deleted_doc_ids_by_class(SurveyKeyword)

    domain_forms = {}
    def add_field(doc):
        return _add_field(doc, domain_names)

    iter_update(SurveyKeyword.get_db(), _add_field, with_progress_bar(doc_ids))


def _add_field(doc):
    if doc.get('form_unique_id', None):
        domain = doc['domain']
        form_unique_id = doc['form_unique_id']
        if domain not in domain_forms:
            domain_forms[domain] = {}
            apps = get_apps_in_domain(domain)
            for app in apps:
                for module in app.modules:
                    for form in module.get_forms():
                        domain_forms[domain][form.unique_id] = app.get_id
        doc['app_id'] = domain_forms[domain].get(form_unique_id, None)
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
