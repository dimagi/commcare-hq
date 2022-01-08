from django.utils.translation import ugettext as _

from custom.samveg.case_importer.exceptions import UnexpectedFileError
from custom.samveg.const import (
    MANDATORY_COLUMNS,
    RCH_BENEFICIARY_IDENTIFIER,
    RCH_MANDATORY_COLUMNS,
    SNCU_BENEFICIARY_IDENTIFIER,
    SNCU_MANDATORY_COLUMNS,
)


class BaseValidator:
    @classmethod
    def run(cls, *args, **kwargs):
        raise NotImplementedError


class MandatoryColumnsValidator(BaseValidator):
    @classmethod
    def run(cls, spreadsheet):
        errors = []
        errors.extend(cls._validate_missing_columns(spreadsheet))
        return errors

    @classmethod
    def _validate_missing_columns(cls, spreadsheet):
        columns = spreadsheet.get_header_columns()
        try:
            mandatory_columns = get_mandatory_columns(columns)
        except UnexpectedFileError:
            return [_('Unexpected sheet uploaded')]

        missing_columns = set(mandatory_columns) - set(columns)
        if missing_columns:
            return [_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns)
            )]


class MandatoryValueValidator(BaseValidator):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update):
        error_messages = []
        error_messages.extend(cls._validate_mandatory_columns(row_num, raw_row))
        return fields_to_update, error_messages

    @classmethod
    def _validate_mandatory_columns(cls, row_num, raw_row):
        error_messages = []
        missing_values = set()

        columns = set(raw_row.keys())
        mandatory_columns = get_mandatory_columns(columns)

        for mandatory_column in mandatory_columns:
            if not raw_row.get(mandatory_column):
                missing_values.add(mandatory_column)
        if missing_values:
            error_messages.append(_('Missing values for {column_names}').format(
                row_number=row_num,
                column_names=', '.join(missing_values)
            ))
        return error_messages


def get_mandatory_columns(columns):
    if RCH_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = RCH_MANDATORY_COLUMNS
    elif SNCU_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = SNCU_MANDATORY_COLUMNS
    else:
        raise UnexpectedFileError
    return MANDATORY_COLUMNS + sheet_specific_columns
