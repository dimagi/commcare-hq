
from django.db import migrations

from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.django_migrations import update_es_mapping
from corehq.apps.users.models import CouchUser
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types


def all_webusers():
    return get_all_docs_with_doc_types(db=CouchUser.get_db(), doc_types=["WebUser"])


def reindex_web_users(*args, **kwargs):
    for user in all_webusers():
        CouchUser.wrap(user).save()


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [
        update_es_mapping(USER_INDEX_INFO.index),
        migrations.RunPython(reindex_web_users),
    ]
