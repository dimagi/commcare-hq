from django.utils.translation import ugettext_lazy, ugettext_noop

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


class ImporterRefError(ImporterError):
    """Raised when a Soil download ref is None"""


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

    def __init__(self, column_name=None):
        self.column_name = column_name
        super(CaseRowError, self).__init__(self.message)


class InvalidOwnerName(CaseRowError):
    title = ugettext_noop('Invalid Owner Name')
    message = ugettext_lazy(
        "Owner name was used in the mapping but there were errors when "
        "uploading because of these values."
    )


class InvalidOwner(CaseRowError):
    title = ugettext_noop('Invalid Owner')
    message = ugettext_lazy(
        "Owners were provided in the mapping but there were errors when "
        "uploading because of these values. Make sure the owners in this "
        "column are users, case sharing groups, or locations."
    )


class InvalidParentId(CaseRowError):
    title = ugettext_noop('Invalid Parent ID')
    message = ugettext_lazy(
        "An invalid or unknown parent case was specified for the "
        "uploaded case."
    )


class InvalidDate(CaseRowError):
    title = ugettext_noop('Invalid Date')
    message = ugettext_lazy(
        "Date fields were specified that caused an error during "
        "conversion. This is likely caused by a value from Excel having "
        "the wrong type or not being formatted properly."
    )


class InvalidSelectValue(CaseRowError):
    title = ugettext_noop('Unexpected multiple choice value')
    message = ugettext_lazy(
        "Multiple choice values were specified that are not listed "
        "in the valid values defined in the property's data dictionary."
    )


class BlankExternalId(CaseRowError):
    title = ugettext_noop('Blank External ID')
    message = ugettext_lazy(
        "Blank external ids were found in these rows causing as error "
        "when importing cases."
    )


class CaseGeneration(CaseRowError):
    title = ugettext_noop('Case Generation Error')
    message = ugettext_lazy(
        "These rows failed to generate cases for unknown reasons"
    )


class DuplicateLocationName(CaseRowError):
    title = ugettext_noop('Duplicated Location Name')
    message = ugettext_lazy(
        "Owner ID was used in the mapping, but there were errors when "
        "uploading because of these values. There are multiple locations "
        "with this same name, try using site-code instead."
    )


class InvalidLocation(CaseRowError):
    title = ugettext_noop('Invalid Location')
    message = ugettext_lazy(
        "The location of the case owner needs to be at or below the "
        "location of the user importing the cases."
    )


class InvalidInteger(CaseRowError):
    title = ugettext_noop('Invalid Integer')
    message = ugettext_lazy(
        "Integer values were specified, but the values in Excel were not "
        "all integers"
    )


class ImportErrorMessage(CaseRowError):
    title = ugettext_noop('Import Error')
    message = ugettext_lazy(
        "Problems in importing cases. Please check the Excel file."
    )


class TooManyMatches(CaseRowError):
    title = ugettext_noop('Too Many Matches')
    message = ugettext_lazy(
        "These rows matched more than one case at the same time - this means "
        "that there are cases in your system with the same external ID."
    )


class CaseNameTooLong(CaseRowError):
    title = ugettext_noop('Name Too Long')
    message = ugettext_lazy(f"The case name cannot be longer than {STANDARD_CHARFIELD_LENGTH} characters")


class ExternalIdTooLong(CaseRowError):
    title = ugettext_noop('External ID Too Long')
    message = ugettext_lazy(f"The external id cannot be longer than {STANDARD_CHARFIELD_LENGTH} characters")
