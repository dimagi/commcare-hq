from django.utils.translation import ugettext as _

from custom.samveg.const import MANDATORY_COLUMNS


class MandatoryColumnsValidator:
    @classmethod
    def validate(cls, spreadsheet):
        errors = []
        columns = spreadsheet.get_header_columns()
        missing_columns = set()
        for mandatory_columns in MANDATORY_COLUMNS:
            missing_columns.update(set(mandatory_columns) - set(columns))
        if missing_columns:
            errors.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns))
            )
        return errors
