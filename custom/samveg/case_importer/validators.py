import datetime
from collections import Counter, defaultdict

from django.utils.translation import ugettext as _

from corehq.util.dates import get_previous_month_date_range
from custom.samveg.case_importer.exceptions import (
    CallNotInLastMonthError,
    CallValueInvalidError,
    CallValuesMissingError,
    OwnerNameMissingError,
    RequiredValueMissingError,
    UnexpectedFileError,
    UploadLimitReachedError,
)
from custom.samveg.case_importer.operations import BaseRowOperation
from custom.samveg.const import (
    CALL_VALUE_FORMAT,
    OWNER_NAME,
    RCH_BENEFICIARY_IDENTIFIER,
    RCH_REQUIRED_COLUMNS,
    REQUIRED_COLUMNS,
    ROW_LIMIT_PER_OWNER_PER_CALL_TYPE,
    SNCU_BENEFICIARY_IDENTIFIER,
    SNCU_REQUIRED_COLUMNS,
)


class RequiredColumnsValidator(object):
    @classmethod
    def run(cls, spreadsheet):
        errors = []
        errors.extend(cls._validate_required_columns(spreadsheet))
        return errors

    @classmethod
    def _validate_required_columns(cls, spreadsheet):
        columns = spreadsheet.get_header_columns()
        error_messages = []
        try:
            required_columns = get_required_columns(columns)
        except UnexpectedFileError:
            return [_('Unexpected sheet uploaded')]

        missing_columns = set(required_columns) - set(columns)
        if missing_columns:
            error_messages.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns)
            ))
        return error_messages


class RequiredValueValidator(BaseRowOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, **kwargs):
        error_messages = []
        error_messages.extend(cls._validate_required_columns(row_num, raw_row))
        return fields_to_update, error_messages

    @classmethod
    def _validate_required_columns(cls, row_num, raw_row):
        error_messages = []
        missing_values = set()

        columns = set(raw_row.keys())
        required_columns = get_required_columns(columns)

        for required_column in required_columns:
            if not raw_row.get(required_column):
                missing_values.add(required_column)
        if missing_values:
            error_messages.append(
                RequiredValueMissingError(
                    message=_('Required columns are {column_names}').format(
                        column_names=', '.join(required_columns)
                    )
                )
            )
        return error_messages


class CallValidator(BaseRowOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, **kwargs):
        error_messages = []
        call_value, call_number = _get_latest_call_value_and_number(raw_row)
        if not call_value:
            error_messages.append(
                CallValuesMissingError()
            )
        else:
            try:
                call_date = datetime.datetime.strptime(call_value, CALL_VALUE_FORMAT).date()
            except ValueError:
                error_messages.append(
                    CallValueInvalidError()
                )
            else:
                last_month_first_day, last_month_last_day = get_previous_month_date_range(datetime.date.today())
                if call_date.replace(day=1) != last_month_first_day:
                    error_messages.append(CallNotInLastMonthError())

        return fields_to_update, error_messages


class UploadLimitValidator(BaseRowOperation):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, **kwargs):
        import_context = kwargs['import_context']
        error_messages = []
        owner_name = raw_row.get(OWNER_NAME)
        call_value, call_number = _get_latest_call_value_and_number(raw_row)
        if owner_name and call_number:
            if cls._upload_limit_reached(import_context, owner_name, call_number):
                error_messages.append(UploadLimitReachedError())
            else:
                cls._update_counter(import_context, owner_name, call_number)
        else:
            if not owner_name:
                error_messages.append(OwnerNameMissingError())
            if not call_number:
                error_messages.append(CallValuesMissingError())
        return fields_to_update, error_messages

    @classmethod
    def _upload_limit_reached(cls, import_context, owner_name, call_number):
        return cls._counter(import_context)[owner_name][f"Call{call_number}"] >= ROW_LIMIT_PER_OWNER_PER_CALL_TYPE

    @classmethod
    def _update_counter(cls, import_context, owner_name, call_number):
        cls._counter(import_context)[owner_name][f"Call{call_number}"] += 1

    @classmethod
    def _counter(cls, import_context):
        if 'counter' not in import_context:
            import_context['counter'] = defaultdict(Counter)
        return import_context['counter']


def get_required_columns(columns):
    if RCH_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = RCH_REQUIRED_COLUMNS
    elif SNCU_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = SNCU_REQUIRED_COLUMNS
    else:
        raise UnexpectedFileError
    return REQUIRED_COLUMNS + sheet_specific_columns


def _get_latest_call_value_and_number(raw_row):
    # A row is assumed to have call columns named, Call1 till Call6
    # return latest call's value and call number
    latest_call_value = None
    latest_call_number = None
    for i in range(1, 7):
        if raw_row.get(f"Call{i}"):
            latest_call_value = raw_row[f"Call{i}"]
            latest_call_number = i
    return latest_call_value, latest_call_number
