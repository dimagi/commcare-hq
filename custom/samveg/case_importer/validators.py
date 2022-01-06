from collections import Counter, defaultdict

from django.utils.translation import ugettext as _

from corehq.apps.case_importer.exceptions import CaseRowError
from custom.samveg.const import (
    MANDATORY_COLUMNS,
    OWNER_NAME,
    RCH_BENEFICIARY_IDENTIFIER,
    RCH_MANDATORY_COLUMNS,
    ROW_LIMIT_PER_OWNER_PER_CALL_TYPE,
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
    def run(cls, row_num, raw_row, fields_to_update, import_context):
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

        if not errors:
            owner_name = raw_row.get(OWNER_NAME)
            call_number = cls._get_call_number(raw_row)
            if owner_name and call_number:
                if cls._upload_limit_reached(import_context, owner_name, call_number):
                    errors.append(
                        CaseRowError(_('Limit reached for {owner_name} for call {call_number}').format(
                            owner_name=owner_name,
                            call_number=call_number
                        ))
                    )
                else:
                    cls._update_counter(import_context, owner_name, call_number)
        return fields_to_update, errors

    @classmethod
    def _upload_limit_reached(cls, import_context, owner_name, call_number):
        return cls._counter(import_context)[owner_name][call_number] >= ROW_LIMIT_PER_OWNER_PER_CALL_TYPE

    @classmethod
    def _get_call_number(cls, raw_row):
        # get call type/number
        # returns an integer, 1-6
        call_number = None
        call_values = cls._get_call_values(raw_row)
        for i, call_value in enumerate(call_values, start=1):
            if call_value:
                call_number = i
        return call_number

    @classmethod
    def _get_call_values(cls, raw_row):
        return [raw_row.get(f"Call{i}") for i in range(1, 7)]

    @classmethod
    def _counter(cls, import_context):
        if 'counter' not in import_context:
            import_context['counter'] = defaultdict(Counter)
        return import_context['counter']

    @classmethod
    def _update_counter(cls, import_context, owner_name, call_number):
        cls._counter(import_context)[owner_name][call_number] += 1

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
        call_values = cls._get_call_values(raw_row)
        call_values_present = list(filter(None, call_values))
        call_number = cls._get_call_number(raw_row)
        if call_values_present:
            if len(call_values_present) != call_number:
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
