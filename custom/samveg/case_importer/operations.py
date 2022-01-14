from datetime import datetime

import pytz


class BaseOperation(object):
    @classmethod
    def run(cls, *args, **kwargs):
        raise NotImplementedError


class AddCustomCaseProperties(BaseOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update):
        today = datetime.utcnow().astimezone(pytz.timezone('Asia/Kolkata')).date()
        fields_to_update['last_upload_change'] = str(today)
        return fields_to_update
