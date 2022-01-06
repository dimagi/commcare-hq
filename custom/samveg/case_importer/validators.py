from django.utils.translation import ugettext as _

from corehq.apps.case_importer.exceptions import CaseRowError
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

        columns = spreadsheet.get_header_columns()
        mandatory_columns = get_mandatory_columns(columns)
        missing_columns = set(mandatory_columns) - set(columns)
        if missing_columns:
            errors.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns))
            )

        return errors


class MandatoryValueValidator(BaseValidator):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update):
        errors = []
        missing_values = set()

        columns = set(raw_row.keys())
        mandatory_columns = get_mandatory_columns(columns)

        for mandatory_column in mandatory_columns:
            if not raw_row.get(mandatory_column):
                missing_values.add(mandatory_column)

        if missing_values:
            errors.append(
                CaseRowError(_('Missing values for {column_names}').format(
                    row_number=row_num,
                    column_names=', '.join(missing_values))
                )
            )
        errors.extend(cls._validate_call_columns(raw_row))
        return fields_to_update, errors

    @classmethod
    def _validate_call_columns(cls, raw_row):
        # out of 6 call columns call1-6, there should be value for at least one
        # and it should be the latest one
        # Example:
        # Invalid:
        # []
        # ['2021-12-01', '', '2022-01-01']
        # Valid:
        # ['2021-12-01']
        # ['2021-12-01', '2022-01-01']
        errors = []
        latest_call_with_value = 0
        call_values = []
        for i in range(1, 7):
            call_value = raw_row.get(f"Call{i}")
            if call_value:
                latest_call_with_value = i
                call_values.append(call_value)
        if call_values:
            if len(call_values) != latest_call_with_value:
                errors.append(CaseRowError(_('Call values not as expected')))
        else:
            errors.append(CaseRowError(_('Call values missing')))
        return errors


def get_mandatory_columns(columns):
    if RCH_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = RCH_MANDATORY_COLUMNS
    elif SNCU_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = SNCU_MANDATORY_COLUMNS
    else:
        raise Exception("Unexpected sheet uploaded")
    return MANDATORY_COLUMNS + sheet_specific_columns
