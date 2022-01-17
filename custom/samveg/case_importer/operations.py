from datetime import datetime

import pytz


class BaseRowOperation(object):
    """
    Perform an operation on each row of case upload.
    """

    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, **kwargs):
        """
        :param row_num: 1-based row number. Headers are in row zero.
        :param raw_row: Row dict.
        :param fields_to_update: Current set of fields to update
        :param kwargs: Optional additional kwargs passed for a specific operation

        :return: fields to update, list of errors
        """
        raise NotImplementedError


class AddCustomCaseProperties(BaseRowOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, **kwargs):
        today = datetime.utcnow().astimezone(pytz.timezone('Asia/Kolkata')).date()
        fields_to_update['last_upload_change'] = str(today)
        return fields_to_update, []
