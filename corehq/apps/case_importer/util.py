from __future__ import absolute_import, unicode_literals

import json
from collections import OrderedDict, namedtuple
from contextlib import contextmanager

from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

import six

from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.exceptions import (
    ImporterExcelError,
    ImporterExcelFileEncrypted,
    ImporterFileNotFound,
    ImporterRefError,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.workbook_reading import (
    SpreadsheetFileEncrypted,
    SpreadsheetFileInvalidError,
    SpreadsheetFileNotFound,
    Workbook,
    open_any_workbook,
)

# Don't allow users to change the case type by accident using a custom field. But do allow users to change
# owner_id, external_id, etc. (See also custom_data_fields.models.RESERVED_WORDS)
RESERVED_FIELDS = ('type',)
EXTERNAL_ID = 'external_id'


class ImporterConfig(namedtuple('ImporterConfig', [
    'couch_user_id',
    'excel_fields',
    'case_fields',
    'custom_fields',
    'search_column',
    'case_type',
    'search_field',
    'create_new_cases',
])):
    """
    Class for storing config values from the POST in a format that can
    be pickled and passed to celery tasks.
    """

    def __new__(cls, *args, **kwargs):
        args, kwargs = cls.__detect_schema_change(args, kwargs)
        return super(cls, ImporterConfig).__new__(cls, *args, **kwargs)

    @staticmethod
    def __detect_schema_change(args, kwargs):
        # before we removed key_column, value_column, named_columns
        # from positions 5-7
        if len(args) == 11 and not kwargs:
            return args[:5] + args[8:], {}
        else:
            return args, kwargs

    def to_dict(self):
        return self._asdict()

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, json_dict):
        return cls(**json_dict)

    @classmethod
    def from_json(cls, json_rep):
        return cls.from_dict(json.loads(json_rep))

    @classmethod
    def from_request(cls, request):
        return cls(
            couch_user_id=request.couch_user._id,
            excel_fields=request.POST.getlist('excel_field[]'),
            case_fields=request.POST.getlist('case_field[]'),
            custom_fields=request.POST.getlist('custom_field[]'),
            search_column=request.POST['search_column'],
            case_type=request.POST['case_type'],
            search_field=request.POST['search_field'],
            create_new_cases=request.POST['create_new_cases'] == 'True',
        )


ALLOWED_EXTENSIONS = ['xls', 'xlsx']


class WorksheetWrapper(object):

    def __init__(self, worksheet):
        self._worksheet = worksheet

    @classmethod
    def from_workbook(cls, workbook):
        if not isinstance(workbook, Workbook):
            raise AssertionError(
                "WorksheetWrapper.from_workbook called without Workbook object")
        elif not workbook.worksheets:
            raise SpreadsheetFileInvalidError(
                _("It seems as though your spreadsheet contains no sheets. Please resave it and try again."))
        else:
            return cls(workbook.worksheets[0])

    @cached_property
    def _headers_by_index(self):
        try:
            header_row = next(self.iter_rows())
        except StopIteration:
            header_row = []

        return OrderedDict(
            (i, header) for i, header in enumerate(header_row)
            if header  # remove None columns the library sometimes returns
        )

    def get_header_columns(self):
        return list(self._headers_by_index.values())

    @property
    def max_row(self):
        return self._worksheet.max_row

    def iter_rows(self):
        for row in self._worksheet.iter_rows():
            yield [cell.value for cell in row]

    def iter_row_dicts(self):
        for row in self.iter_rows():
            yield {
                self._headers_by_index[i]: value
                for i, value in enumerate(row)
                if i in self._headers_by_index
            }


def lookup_case(search_field, search_id, domain, case_type):
    """
    Attempt to find the case in CouchDB by the provided search_field and search_id.

    Returns a tuple with case (if found) and an
    error code (if there was an error in lookup).
    """
    found = False
    case_accessors = CaseAccessors(domain)
    if search_field == 'case_id':
        try:
            case = case_accessors.get_case(search_id)
            if case.domain == domain and case.type == case_type:
                found = True
        except CaseNotFound:
            pass
    elif search_field == EXTERNAL_ID:
        cases_by_type = case_accessors.get_cases_by_external_id(search_id, case_type=case_type)
        if not cases_by_type:
            return (None, LookupErrors.NotFound)
        elif len(cases_by_type) > 1:
            return (None, LookupErrors.MultipleResults)
        else:
            case = cases_by_type[0]
            found = True

    if found:
        return (case, None)
    else:
        return (None, LookupErrors.NotFound)


def open_spreadsheet_download_ref(filename):
    """
    open a spreadsheet download ref just to test there are no errors opening it
    """
    with get_spreadsheet(filename):
        pass


@contextmanager
def get_spreadsheet(filename):
    try:
        with open_any_workbook(filename) as workbook:
            yield WorksheetWrapper.from_workbook(workbook)
    except SpreadsheetFileEncrypted as e:
        raise ImporterExcelFileEncrypted(six.text_type(e))
    except SpreadsheetFileNotFound as e:
        raise ImporterFileNotFound(six.text_type(e))
    except SpreadsheetFileInvalidError as e:
        raise ImporterExcelError(six.text_type(e))


def get_importer_error_message(e):
    if isinstance(e, ImporterRefError):
        # I'm not totally sure this is the right error, but it's what was being
        # used before. (I think people were just calling _spreadsheet_expired
        # or otherwise blaming expired sessions whenever anything unexpected
        # happened though...)
        return _('Sorry, your session has expired. Please start over and try again.')
    elif isinstance(e, ImporterFileNotFound):
        return _('The session containing the file you uploaded has expired. '
                 'Please upload a new one.')
    elif isinstance(e, ImporterExcelFileEncrypted):
        return _('The file you want to import is password protected. '
                 'Please choose a file that is not password protected.')
    elif isinstance(e, ImporterExcelError):
        return _("The file uploaded has the following error: {}").format(six.text_type(e))
    else:
        return _("Error: {}").format(six.text_type(e))
