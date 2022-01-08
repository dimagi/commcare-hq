class BaseValidator:
    @classmethod
    def run(cls, *args, **kwargs):
        raise NotImplementedError


class MandatoryColumnsValidator(BaseValidator):
    @classmethod
    def run(cls, spreadsheet):
        errors = []
        # ToDo: validate columns
        return errors
