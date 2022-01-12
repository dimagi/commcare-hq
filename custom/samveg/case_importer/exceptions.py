from django.utils.translation import ugettext_noop

from corehq.apps.case_importer.exceptions import CaseRowError


class UnexpectedFileError(Exception):
    pass


class RequiredValueMissingError(CaseRowError):
    title = ugettext_noop('Missing required value(s)')


class CallValuesMissingError(CaseRowError):
    title = ugettext_noop('Missing call values')


class OwnerNameMissingError(CaseRowError):
    title = ugettext_noop('Missing owner name')


class CallValueInvalidError(CaseRowError):
    title = ugettext_noop('Latest call value not a date')


class CallNotInLastMonthError(CaseRowError):
    title = ugettext_noop('Latest call not in last month')


class UploadLimitReachedError(CaseRowError):
    title = ugettext_noop('Upload limit reached for owner and call type')
