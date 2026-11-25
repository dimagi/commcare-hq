from django.conf import settings
from django.db import migrations

from corehq.apps.es.mappings.case_search_mapping import CASE_SEARCH_MAPPING
from corehq.apps.es.migration_operations import (
    CreateIndex,
    DeleteOnlyIfIndexExists,
)
from corehq.apps.es.utils import index_runtime_name


def _create_philly_ubr_index(apps, schema_editor):
    if settings.ENABLE_BHA_CASE_SEARCH_ADAPTER:
        CreateIndex(
            name=index_runtime_name('case-search-philly-ubr-2026-10-01'),
            type_='case',
            mapping=CASE_SEARCH_MAPPING,
            analysis={
                'filter': {'soundex': {'encoder': 'soundex', 'replace': 'true', 'type': 'phonetic'}},
                'analyzer': {'default': {'filter': ['lowercase'], 'tokenizer': 'whitespace', 'type': 'custom'}, 'phonetic': {'filter': ['standard', 'lowercase', 'soundex'], 'tokenizer': 'standard'}},
            },
            settings_key='case_search_philly_ubr',
            es_versions=[6],
        ).run()


def _reverse(apps, schema_editor):
    if settings.ENABLE_BHA_CASE_SEARCH_ADAPTER:
        DeleteOnlyIfIndexExists(index_runtime_name('case-search-philly-ubr-2026-10-01')).run()


class Migration(migrations.Migration):

    dependencies = [
        ('es', '0017_add_is_account_confirmed'),
    ]

    operations = [
        migrations.RunPython(_create_philly_ubr_index, reverse_code=_reverse)
    ]
