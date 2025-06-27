from django.conf import settings
from django.db import migrations

from corehq.apps.es.mappings.case_search_mapping import CASE_SEARCH_MAPPING
from corehq.apps.es.migration_operations import (
    CreateIndex,
    DeleteOnlyIfIndexExists,
)
from corehq.apps.es.utils import index_runtime_name


def _create_cc_perf_index(apps, schema_editor):
    if settings.ENABLE_BHA_CASE_SEARCH_ADAPTER:
        CreateIndex(
            name=index_runtime_name('case-search-cc-perf-2025-06-19'),
            type_='case',
            mapping=CASE_SEARCH_MAPPING,
            analysis={
                'filter': {'soundex': {'encoder': 'soundex', 'replace': 'true', 'type': 'phonetic'}},
                'analyzer': {'default': {'filter': ['lowercase'], 'tokenizer': 'whitespace', 'type': 'custom'}, 'phonetic': {'filter': ['standard', 'lowercase', 'soundex'], 'tokenizer': 'standard'}},
            },
            settings_key='case_search_cc_perf',
            es_versions=[6],
        ).run()


def _reverse(apps, schema_editor):
    if settings.ENABLE_BHA_CASE_SEARCH_ADAPTER:
        DeleteOnlyIfIndexExists(index_runtime_name('case-search-cc-perf-2025-06-19')).run()


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0015_add_user_domain_memberships'),
    ]

    operations = [
        migrations.RunPython(_create_cc_perf_index, reverse_code=_reverse)
    ]
