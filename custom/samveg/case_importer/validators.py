import datetime
import re
from collections import Counter, defaultdict

from django.utils.translation import gettext as _

from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.domain.models import OperatorCallLimitSettings
from corehq.util.dates import get_previous_month_date_range, iso_string_to_date
from custom.samveg.case_importer.exceptions import (
    CallNotInLastMonthError,
    CallValueInvalidError,
    CallValuesMissingError,
    MobileNumberInvalidError,
    OwnerNameMissingError,
    RequiredValueMissingError,
    UnexpectedFileError,
    UnexpectedSkipCallValidatorValueError,
    UploadLimitReachedError,
)
from custom.samveg.case_importer.operations import BaseRowOperation
from custom.samveg.const import (
    MOBILE_NUMBER,
    OWNER_NAME,
    RCH_BENEFICIARY_IDENTIFIER,
    RCH_REQUIRED_COLUMNS,
    REQUIRED_COLUMNS,
    SKIP_CALL_VALIDATOR,
    SKIP_CALL_VALIDATOR_YES,
    SNCU_BENEFICIARY_IDENTIFIER,
    SNCU_REQUIRED_COLUMNS,
)


class BaseSheetValidator:
    @classmethod
    def run(cls, spreadsheet):
        """Validate spreadsheet.

        :param spreadsheet: Spreadsheet object provided by
        corehq.apps.case_importer.tracking.case_upload_tracker.CaseUpload.get_spreadsheet
        :return: List of error messages.
        """
        return []


class RequiredColumnsValidator(BaseSheetValidator):
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
            return [_(
                'Unexpected sheet uploaded. Either {rch_identifier} or {sncu_identifier} should be present'
            ).format(
                rch_identifier=RCH_BENEFICIARY_IDENTIFIER,
                sncu_identifier=SNCU_BENEFICIARY_IDENTIFIER
            )]

        missing_columns = set(required_columns) - set(columns)
        if missing_columns:
            error_messages.append(_('Missing columns {column_names}').format(
                column_names=", ".join(missing_columns)
            ))
        return error_messages


class CallColumnsValidator(BaseSheetValidator):
    @classmethod
    def run(cls, spreadsheet):
        errors = []
        errors.extend(cls._validate_call_columns(spreadsheet))
        return errors

    @classmethod
    def _validate_call_columns(cls, spreadsheet):
        # at least one call column, Call1-6
        columns = spreadsheet.get_header_columns()
        error_messages = []
        call_regex = re.compile(r'^Call[1-6]$')
        if not any(call_regex.match(column_name) for column_name in columns):
            error_messages.append(
                _('Need at least one Call column for Calls 1-6')
            )
        return error_messages


class RequiredValueValidator(BaseRowOperation):

    def __init__(self, row_num=None, raw_row=None, **kwargs):
        super(RequiredValueValidator, self).__init__(**kwargs)
        self.row_num = row_num
        self.raw_row = raw_row

    def run(self):
        self.error_messages.extend(self._validate_required_columns())
        return self.fields_to_update, self.error_messages

    def _validate_required_columns(self):
        error_messages = []
        missing_values = set()

        columns = set(self.raw_row.keys())
        required_columns = get_required_columns(columns)
        required_columns.append(EXTERNAL_ID)

        for required_column in required_columns:
            if not self.fields_to_update.get(required_column):
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

    def __init__(self, raw_row=None, **kwargs):
        super(CallValidator, self).__init__(**kwargs)
        self.raw_row = raw_row

    def run(self):
        if self.raw_row.get(SKIP_CALL_VALIDATOR):
            # skip the row
            # add error message if the value isn't the only expected value
            if self.raw_row.get(SKIP_CALL_VALIDATOR) != SKIP_CALL_VALIDATOR_YES:
                self.error_messages.append(
                    UnexpectedSkipCallValidatorValueError()
                )
            return self.fields_to_update, self.error_messages

        call_date = None
        call_value, _ = _get_latest_call_value_and_number(self.fields_to_update)
        if not call_value:
            self.error_messages.append(
                CallValuesMissingError()
            )
        else:
            try:
                call_date = iso_string_to_date(call_value)
            except ValueError:
                self.error_messages.append(
                    CallValueInvalidError()
                )
        if call_date:
            last_month_first_day, _ = get_previous_month_date_range(datetime.date.today())
            if call_date.replace(day=1) != last_month_first_day:
                self.error_messages.append(CallNotInLastMonthError())

        return self.fields_to_update, self.error_messages


class FormatValidator(BaseRowOperation):

    def run(self):
        mobile_number = self.fields_to_update.get(MOBILE_NUMBER)
        if mobile_number and len(str(mobile_number)) != 10:
            self.error_messages.append(MobileNumberInvalidError())
        return self.fields_to_update, self.error_messages


class UploadLimitValidator(BaseRowOperation):

    def __init__(self, import_context=None, domain=None, **kwargs):
        super(UploadLimitValidator, self).__init__(**kwargs)
        self.import_context = import_context
        self.domain = domain

    def run(self):
        owner_name = self.fields_to_update.get(OWNER_NAME)
        _, call_number = _get_latest_call_value_and_number(self.fields_to_update)
        if owner_name and call_number:
            if self._upload_limit_reached(owner_name, call_number):
                self.error_messages.append(UploadLimitReachedError())
            else:
                self._update_counter(owner_name, call_number)
        else:
            if not owner_name:
                self.error_messages.append(OwnerNameMissingError())
            if not call_number:
                self.error_messages.append(CallValuesMissingError())
        return self.fields_to_update, self.error_messages

    def _upload_limit_reached(self, owner_name, call_number):
        setting_obj, _ = OperatorCallLimitSettings.objects.get_or_create(domain=self.domain)
        return self._counter()[owner_name][f"Call{call_number}"] >= setting_obj.call_limit

    def _update_counter(self, owner_name, call_number):
        self._counter()[owner_name][f"Call{call_number}"] += 1

    def _counter(self):
        if 'counter' not in self.import_context:
            self.import_context['counter'] = defaultdict(Counter)
        return self.import_context['counter']


def get_required_columns(columns):
    if RCH_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = RCH_REQUIRED_COLUMNS
    elif SNCU_BENEFICIARY_IDENTIFIER in columns:
        sheet_specific_columns = SNCU_REQUIRED_COLUMNS
    else:
        raise UnexpectedFileError
    return REQUIRED_COLUMNS + sheet_specific_columns


def _get_latest_call_value_and_number(fields_to_update):
    # A row is assumed to have call columns named, Call1 till Call6
    # return latest call's value and call number
    latest_call_value = None
    latest_call_number = None
    for i in range(1, 7):
        if fields_to_update.get(f"Call{i}"):
            latest_call_value = fields_to_update[f"Call{i}"]
            latest_call_number = i
    return latest_call_value, latest_call_number
