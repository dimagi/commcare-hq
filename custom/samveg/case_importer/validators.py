import datetime
from collections import Counter, defaultdict

from django.utils.translation import ugettext as _

from corehq.util.dates import get_previous_month_date_range
from custom.samveg.case_importer.exceptions import UnexpectedFileError
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

    @classmethod
    def _get_latest_call_value_and_number(cls, raw_row):
        # A row is assumed to have call columns named, Call1 till Call6
        # return latest call's value and call number
        latest_call_value = None
        latest_call_number = None
        for i in range(1, 7):
            if raw_row.get(f"Call{i}"):
                latest_call_value = raw_row[f"Call{i}"]
                latest_call_number = i
        return latest_call_value, latest_call_number


class MandatoryColumnsValidator(BaseValidator):
    @classmethod
    def run(cls, spreadsheet):
        errors = []
        errors.extend(cls._validate_mandatory_columns(spreadsheet))
        return errors

    @classmethod
    def _validate_mandatory_columns(cls, spreadsheet):
        columns = spreadsheet.get_header_columns()
        error_messages = []
        try:
            mandatory_columns = get_mandatory_columns(columns)
        except UnexpectedFileError:
            return [_('Unexpected sheet uploaded')]

        missing_columns = set(mandatory_columns) - set(columns)
        if missing_columns:
            error_messages.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns)
            ))
        return error_messages


class MandatoryValueValidator(BaseValidator):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, import_context):
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
            error_messages.append(_('Mandatory columns {column_names}').format(
                row_number=row_num,
                column_names=', '.join(mandatory_columns)
            ))
        return error_messages


class CallValidator(BaseValidator):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, import_context):
        error_messages = []
        call_value, call_number = cls._get_latest_call_value_and_number(raw_row)
        if not call_value:
            error_messages.append(
                _('Missing call details')
            )
        else:
            try:
                call_date = datetime.datetime.strptime(call_value, '%d-%m-%y')
            except ValueError:
                error_messages.append(
                    _('Could not parse latest call date')
                )
            else:
                last_month_first_day, last_month_last_day = get_previous_month_date_range(datetime.date.today())
                if call_date.replace(day=1) != last_month_first_day:
                    error_messages.append(
                        _('Latest call not in last month')
                    )

        return fields_to_update, error_messages


class UploadLimitValidator(BaseValidator):
    @classmethod
    def run(cls, row_num, raw_row, fields_to_update, import_context):
        error_messages = []
        owner_name = raw_row.get(OWNER_NAME)
        call_value, call_number = cls._get_latest_call_value_and_number(raw_row)
        if owner_name and call_number:
            if cls._upload_limit_reached(import_context, owner_name, call_number):
                error_messages.append(
                    _('Limit reached for {owner_name} for call {call_number}').format(
                        owner_name=owner_name,
                        call_number=call_number
                    )
                )
            else:
                cls._update_counter(import_context, owner_name, call_number)
        else:
            error_messages.append(
                _('Missing owner or call details')
            )
        return fields_to_update, error_messages

    @classmethod
    def _upload_limit_reached(cls, import_context, owner_name, call_number):
        return cls._counter(import_context)[owner_name][call_number] >= ROW_LIMIT_PER_OWNER_PER_CALL_TYPE

    @classmethod
    def _update_counter(cls, import_context, owner_name, call_number):
        cls._counter(import_context)[owner_name][call_number] += 1

    @classmethod
    def _counter(cls, import_context):
        if 'counter' not in import_context:
            import_context['counter'] = defaultdict(Counter)
        return import_context['counter']


def get_mandatory_columns(columns):
    if RCH_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = RCH_MANDATORY_COLUMNS
    elif SNCU_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = SNCU_MANDATORY_COLUMNS
    else:
        raise UnexpectedFileError
    return MANDATORY_COLUMNS + sheet_specific_columns
