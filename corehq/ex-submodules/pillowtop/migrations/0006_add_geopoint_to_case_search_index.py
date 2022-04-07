from django.db import migrations

from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_ALIAS
from corehq.util.django_migrations import update_es_mapping


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0005_kafkacheckpoint_doc_modification_time'),
    ]

    operations = [update_es_mapping(CASE_SEARCH_ALIAS)]
