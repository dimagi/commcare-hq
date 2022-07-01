from datetime import datetime

import pytz


class BaseRowOperation(object):
    """
    Perform an operation on each row of case upload.
    """

    def __init__(self, **kwargs):
        """
        Possible values in kwargs
        :param row_num: 1-based row number. Headers are in row zero.
        :param raw_row: Row dict.
        :param fields_to_update: Current set of fields to update
        :param import_context: import context available during import for extensions
        :param domain_name: name of the domain for which upload operation is done
        """
        self.fields_to_update = kwargs.get("fields_to_update")
        self.error_messages = []

    def run(self):
        raise NotImplementedError


class AddCustomCaseProperties(BaseRowOperation):

    def run(self):
        """
        :return: fields to update, list of errors
        """
        self.fields_to_update['last_upload_change'] = str(_get_today_date())
        self.fields_to_update['visit_type'] = self._get_visit_type()
        return self.fields_to_update, self.error_messages

    def _get_visit_type(self):
        from custom.samveg.case_importer.validators import _get_latest_call_value_and_number

        _, latest_call_number = _get_latest_call_value_and_number(self.fields_to_update)
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
