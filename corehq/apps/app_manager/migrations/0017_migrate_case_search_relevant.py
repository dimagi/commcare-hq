from django.db import migrations

from corehq.apps.app_manager.dbaccessors import get_all_app_ids
from corehq.apps.app_manager.models import Application
from corehq.toggles import SYNC_SEARCH_CASE_CLAIM
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.util.log import with_progress_bar


@skip_on_fresh_install
def _migrate_case_search_relevant(apps, schema_editor):
    for domain in SYNC_SEARCH_CASE_CLAIM.get_enabled_domains():
        app_ids = get_all_app_ids(domain)
        print(f"Migrating {domain}, which has {len(app_ids)} docs")
        iter_update(Application.get_db(), _update_relevant, with_progress_bar(app_ids), chunksize=100)


def _update_relevant(doc):
    save = False
    default = "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0"
    prefix = f"({default}) and ("

    for module in doc.get('modules', []):
        if module.get('search_config'):
            relevant = module['search_config'].get('relevant')
            if relevant:
                save = True
                if relevant == default:
                    module['search_config']['default_relevant'] = True
                    module['search_config']['additional_relevant'] = ""
                elif relevant.startswith(prefix):
                    module['search_config']['default_relevant'] = True
                    module['search_config']['additional_relevant'] = relevant[len(prefix):-1]
                else:
                    module['search_config']['default_relevant'] = False
                    module['search_config']['additional_relevant'] = relevant
    if save:
        return DocUpdate(doc)


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0016_alter_exchangeapplication'),
    ]

    operations = [
        migrations.RunPython(_migrate_case_search_relevant,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
