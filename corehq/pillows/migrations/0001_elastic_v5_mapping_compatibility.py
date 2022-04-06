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

from ..utils import update_mapping_migration_op


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        update_mapping_migration_op(APP_INDEX_INFO.index),
        update_mapping_migration_op(CASE_INDEX_INFO.index),
        update_mapping_migration_op(CASE_SEARCH_INDEX_INFO.index),
        update_mapping_migration_op(DOMAIN_INDEX_INFO.index),
        update_mapping_migration_op(GROUP_INDEX_INFO.index),
        update_mapping_migration_op(REPORT_CASE_INDEX_INFO.index),
        update_mapping_migration_op(REPORT_XFORM_INDEX_INFO.index),
        update_mapping_migration_op(SMS_INDEX_INFO.index),
        update_mapping_migration_op(USER_INDEX_INFO.index),
        update_mapping_migration_op(XFORM_INDEX_INFO.index),
    ]
