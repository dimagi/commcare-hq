# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import HqRunSQL


def _rename_index(old_name, new_name):
    return HqRunSQL(
        sql='ALTER INDEX {} RENAME TO {}'.format(old_name, new_name),
        reverse_sql='ALTER INDEX {} RENAME TO {}'.format(new_name, old_name),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0042_change_choice_values'),
    ]

    operations = [
        _rename_index('form_processor_xforminstancesql_form_uuid_key', 'form_processor_xforminstancesql_form_id_key'),
        _rename_index('form_processor_xformattachmentsql_attachment_uuid_key', 'form_processor_xformattachmentsql_attachment_id_key'),
        _rename_index('form_processor_xformattachmentsql_form_id_2c7940ea539d6de4_uniq', 'form_processor_xformattachmentsql_d6cba1ad'),
        _rename_index('form_processor_xformoperationsql_form_id_6610a535ea713665_uniq', 'form_processor_xformoperationsql_d6cba1ad'),
        _rename_index('form_processor_commcarecasesql_case_uuid_c24829d3eeac14d_uniq', 'form_processor_commcarecasesql_case_id_key'),
        _rename_index('form_processor_caseattach_attachment_uuid_4c1d2c3ea75567cc_uniq', 'form_processor_caseattachmentsql_attachment_id_key'),
        _rename_index('form_processor_caseattachmentsql_case_id_2a52028042cc318d_uniq', 'form_processor_caseattachmentsql_7f12ca67'),
        _rename_index('form_processor_caseattachmentsql_name_1d9638e12751b7c9_uniq', 'form_processor_caseattachmentsql_b068931c'),
        _rename_index('form_processor_casetransaction_case_uuid_658060f617332cb8_uniq', 'form_processor_casetransaction_case_id_1664708167e61d08_uniq'),
        _rename_index('form_processor_casetransaction_case_id_6c13626ba79fe02e_uniq', 'form_processor_casetransaction_7f12ca67'),
        _rename_index('form_processor_commcarecaseindexs_case_id_7db75a61e418ebfc_uniq', 'form_processor_commcarecaseindexsql_7f12ca67'),
    ]
