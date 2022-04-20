from django.db import migrations

from corehq.pillows.mappings import (
    CASE_INDEX_INFO,
    GROUP_INDEX_INFO,
    SMS_INDEX_INFO,
    USER_INDEX_INFO,
)
from corehq.util.django_migrations import update_es_mapping


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [
        update_es_mapping(CASE_INDEX_INFO.index),
        update_es_mapping(GROUP_INDEX_INFO.index),
        update_es_mapping(SMS_INDEX_INFO.index),
        update_es_mapping(USER_INDEX_INFO.index),
    ]
