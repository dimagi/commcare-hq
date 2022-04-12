from django.db import migrations

from corehq.pillows.mappings import (
    APP_INDEX_INFO,
    CASE_INDEX_INFO,
    CASE_SEARCH_INDEX_INFO,
    DOMAIN_INDEX_INFO,
    GROUP_INDEX_INFO,
    REPORT_CASE_INDEX_INFO,
    REPORT_XFORM_INDEX_INFO,
    SMS_INDEX_INFO,
    USER_INDEX_INFO,
    XFORM_INDEX_INFO,
)
from corehq.util.django_migrations import update_es_mapping


class Migration(migrations.Migration):

    dependencies = [
        ('pillowtop', '0006_add_geopoint_to_case_search_index'),
    ]

    operations = [
        update_es_mapping(APP_INDEX_INFO.index),
        update_es_mapping(CASE_INDEX_INFO.index),
        update_es_mapping(CASE_SEARCH_INDEX_INFO.index),
        update_es_mapping(DOMAIN_INDEX_INFO.index),
        update_es_mapping(GROUP_INDEX_INFO.index),
        update_es_mapping(REPORT_CASE_INDEX_INFO.index),
        update_es_mapping(REPORT_XFORM_INDEX_INFO.index),
        update_es_mapping(SMS_INDEX_INFO.index),
        update_es_mapping(USER_INDEX_INFO.index),
        update_es_mapping(XFORM_INDEX_INFO.index),
    ]
