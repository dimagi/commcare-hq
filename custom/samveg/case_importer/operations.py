from datetime import datetime

import pytz


class BaseRowOperation(object):
    """
    Perform an operation on each row of case upload.
    """

    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, import_context):
        """
        :param row_num: 1-based row number. Headers are in row zero.
        :param raw_row: Row dict.
        :param fields_to_update: Current set of fields to update
        :param import_context: import context available during import for extensions

        :return: fields to update, list of errors
        """
        raise NotImplementedError


class AddCustomCaseProperties(BaseRowOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, import_context):
        fields_to_update['last_upload_change'] = str(_get_today_date())
        fields_to_update['visit_type'] = cls._get_visit_type(fields_to_update)
        return fields_to_update, []

    @classmethod
    def _get_visit_type(cls, fields_to_update):
        from custom.samveg.case_importer.validators import _get_latest_call_value_and_number

        latest_call_value, latest_call_number = _get_latest_call_value_and_number(fields_to_update)
        return {
            'Call1': 'anc',
            'Call2': 'hrp',
            'Call3': 'childbirth',
            'Call4': 'sncu',
            'Call5': 'penta_3',
            'Call6': 'opv_booster',
        }[f"Call{latest_call_number}"]


def _get_today_date():
    return datetime.now(pytz.timezone('Asia/Kolkata')).date()
