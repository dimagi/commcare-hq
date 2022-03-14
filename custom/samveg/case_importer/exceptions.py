from django.utils.translation import gettext_noop

from corehq.apps.case_importer.exceptions import CaseRowError


class UnexpectedFileError(Exception):
    pass


class RequiredValueMissingError(CaseRowError):
    title = gettext_noop('Missing required column(s)')


class CallValuesMissingError(CaseRowError):
    title = gettext_noop('Missing call values')


class OwnerNameMissingError(CaseRowError):
    title = gettext_noop('Missing owner name')


class CallValueInvalidError(CaseRowError):
    title = gettext_noop('Latest call value not a date')


class MobileNumberInvalidError(CaseRowError):
    title = gettext_noop('Mobile number should be 10 digits')


class CallNotInLastMonthError(CaseRowError):
    title = gettext_noop('Latest call not in last month')


class UploadLimitReachedError(CaseRowError):
    title = gettext_noop('Upload limit reached for owner and call type')


class UnexpectedSkipCallValidatorValueError(CaseRowError):
    title = gettext_noop('Unexpected value for skipping call validator column')
