# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations




def _rename_index(old_name, new_name):
    return migrations.RunSQL(
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
        _rename_index('form_processor_xforminstancesql_form_uuid_d939b4d9_like', 'form_processor_xformattachmentsql_d6cba1ad'),
        _rename_index('form_processor_xformoperationsql_form_id_bfa39e5e', 'form_processor_xformoperationsql_d6cba1ad'),
        _rename_index('form_processor_commcarecasesql_case_uuid_2d1ffa8d_uniq', 'form_processor_commcarecasesql_case_id_key'),
        _rename_index('form_processor_caseattachmentsql_attachment_uuid_8d145664_uniq', 'form_processor_caseattachmentsql_attachment_id_key'),
        _rename_index('form_processor_caseattachmentsql_case_id_2fe405b2', 'form_processor_caseattachmentsql_7f12ca67'),
        _rename_index('form_processor_caseattachmentsql_name_1dcd3a20', 'form_processor_caseattachmentsql_b068931c'),
        _rename_index('form_processor_casetransaction_case_id_0328b100', 'form_processor_casetransaction_7f12ca67'),
        _rename_index('form_processor_commcarecaseindexsql_case_id_be4cb9e1', 'form_processor_commcarecaseindexsql_7f12ca67'),
    ]
