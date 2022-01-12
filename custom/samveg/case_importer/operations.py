class BaseOperation(object):
    @classmethod
    def run(cls, *args, **kwargs):
        raise NotImplementedError


class AddCustomCaseProperties(BaseOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update):
        # ToDo: Add new case property
        return fields_to_update
