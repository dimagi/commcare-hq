from django.utils.translation import gettext_lazy, gettext_noop

import xlrd

from corehq.form_processor.models import STANDARD_CHARFIELD_LENGTH


class ImporterError(Exception):
    """
    Generic error raised for any problem to do with finding, opening, reading, etc.
    the file being imported

    When possible, a more specific subclass should be used
    """


class ImporterRawError(ImporterError):
    """Stand-in for generic error return codes"""


class ImporterFileNotFound(ImporterError):
    """Raised when a referenced file can't be found"""


class ImporterExcelError(ImporterError, xlrd.XLRDError):
    """
    Generic error raised for any error parsing an Excel file

    When possible, a more specific subclass should be used
    """


class ImporterExcelFileEncrypted(ImporterExcelError):
    """Raised when a file cannot be open because it is encrypted (password-protected)"""


class InvalidCustomFieldNameException(ImporterError):
    """Raised when a custom field name is reserved (e.g. "type")"""
    pass


class CustomImporterError(ImporterError):
    """Raised for errors returned by extensions for file being imported"""


class CaseRowErrorList(Exception):
    def __init__(self, errors=None):
        self.error_list = errors if errors else []
        super().__init__()

    def __iter__(self):
        return iter(self.error_list)


class CaseRowError(Exception):
    """Base Error class for failures associated with an individual upload row"""
    title = ""
    message = ""

    def __init__(self, column_name=None, message=None, sample=None):
        self.column_name = column_name
        if message:
            self.message = message
        if sample:
            self.sample = sample
        super(CaseRowError, self).__init__(self.message)


class InvalidOwnerName(CaseRowError):
    title = gettext_noop('Invalid Owner Name')
    message = gettext_lazy(
        "Owner name was used in the mapping but there were errors when "
        "uploading because of these values."
    )


class InvalidOwner(CaseRowError):
    title = gettext_noop('Invalid Owner')
    message = gettext_lazy(
        "Owners were provided in the mapping but there were errors when "
        "uploading because of these values. Make sure the owners in this "
        "column are users, case sharing groups, or locations."
    )


class InvalidParentId(CaseRowError):
    title = gettext_noop('Invalid Parent ID')
    message = gettext_lazy(
        "An invalid or unknown parent case was specified for the "
        "uploaded case."
    )


class InvalidDate(CaseRowError):
    title = gettext_noop('Invalid Date')
    message = gettext_lazy(
        'Required format: YYYY-MM-DD (e.g. "2021-12-31")'
    )


class InvalidSelectValue(CaseRowError):
    title = gettext_noop('Unexpected multiple choice value')
    message = gettext_lazy(
        "Multiple choice values were specified that are not listed "
        "in the valid values defined in the property's data dictionary."
    )


class BlankExternalId(CaseRowError):
    title = gettext_noop('Blank External ID')
    message = gettext_lazy(
        "Blank external ids were found in these rows causing as error "
        "when importing cases."
    )


class CaseGeneration(CaseRowError):
    title = gettext_noop('Case Generation Error')
    message = gettext_lazy(
        "These rows failed to generate cases for unknown reasons"
    )


class DuplicateLocationName(CaseRowError):
    title = gettext_noop('Duplicated Location Name')
    message = gettext_lazy(
        "Owner ID was used in the mapping, but there were errors when "
        "uploading because of these values. There are multiple locations "
        "with this same name, try using site-code instead."
    )


class InvalidLocation(CaseRowError):
    title = gettext_noop('Invalid Location')
    message = gettext_lazy(
        "The location of the case owner needs to be at or below the "
        "location of the user importing the cases."
    )


class InvalidInteger(CaseRowError):
    title = gettext_noop('Invalid Integer')
    message = gettext_lazy(
        "Integer values were specified, but the values in Excel were not "
        "all integers"
    )


class ImportErrorMessage(CaseRowError):
    title = gettext_noop('Import Error')
    message = gettext_lazy(
        "Problems in importing cases. Please check the Excel file."
    )


class TooManyMatches(CaseRowError):
    title = gettext_noop('Too Many Matches')
    message = gettext_lazy(
        "These rows matched more than one case at the same time - this means "
        "that there are cases in your system with the same external ID."
    )


class CaseNameTooLong(CaseRowError):
    title = gettext_noop('Name Too Long')
    message = gettext_lazy(f"The case name cannot be longer than {STANDARD_CHARFIELD_LENGTH} characters")


class ExternalIdTooLong(CaseRowError):
    title = gettext_noop('External ID Too Long')
    message = gettext_lazy(f"The external id cannot be longer than {STANDARD_CHARFIELD_LENGTH} characters")


class UnexpectedError(CaseRowError):
    title = gettext_noop('Unexpected error')
    message = gettext_lazy('Could not process case. If this persists, please report an issue to CommCare HQ')
