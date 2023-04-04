import json
from collections import OrderedDict, namedtuple
from contextlib import contextmanager

from celery import states
from celery.exceptions import Ignore
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from memoized import memoized

from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.exceptions import (
    ImporterExcelError,
    ImporterExcelFileEncrypted,
    ImporterFileNotFound,
    ImporterRawError,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.util.workbook_reading import (
    SpreadsheetFileEncrypted,
    SpreadsheetFileInvalidError,
    SpreadsheetFileNotFound,
    Workbook,
    open_any_workbook,
)
from soil.progress import update_task_state

# Don't allow users to change the case type by accident using a custom field. But do allow users to change
# owner_id, external_id, etc. (See also custom_data_fields.models.RESERVED_WORDS)
RESERVED_FIELDS = ('type', 'closed', 'parent_ref')
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


class WorksheetWrapper(object):

    def __init__(self, worksheet):
        self._worksheet = worksheet

    @classmethod
    def from_workbook(cls, workbook, worksheet_index=0):
        if not isinstance(workbook, Workbook):
            raise AssertionError(
                "WorksheetWrapper.from_workbook called without Workbook object")
        elif not workbook.worksheets:
            raise SpreadsheetFileInvalidError(
                _("It seems as though your spreadsheet contains no sheets. Please resave it and try again."))
        else:
            return cls(workbook.worksheets[worksheet_index])

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
    Attempt to find the case by the provided search_field and search_id.

    Returns a tuple with case (if found) and an
    error code (if there was an error in lookup).
    """
    if search_field == 'case_id':
        try:
            case = CommCareCase.objects.get_case(search_id, domain)
            if case.type == case_type:
                return (case, None)
        except CaseNotFound:
            pass
    elif search_field == EXTERNAL_ID:
        try:
            case = CommCareCase.objects.get_case_by_external_id(
                domain, search_id, case_type=case_type, raise_multiple=True)
        except CommCareCase.MultipleObjectsReturned:
            return (None, LookupErrors.MultipleResults)
        if case is not None:
            return (case, None)
    return (None, LookupErrors.NotFound)


def open_spreadsheet_download_ref(filename):
    """
    open a spreadsheet download ref just to test there are no errors opening it
    """
    with get_spreadsheet(filename):
        pass


@contextmanager
def get_spreadsheet(filename, worksheet_index=0):
    try:
        with open_any_workbook(filename) as workbook:
            yield WorksheetWrapper.from_workbook(workbook, worksheet_index)
    except SpreadsheetFileEncrypted as e:
        raise ImporterExcelFileEncrypted(str(e))
    except SpreadsheetFileNotFound as e:
        raise ImporterFileNotFound(str(e))
    except SpreadsheetFileInvalidError as e:
        raise ImporterExcelError(str(e))


def get_importer_error_message(e):
    if isinstance(e, ImporterFileNotFound):
        return _('There was an unexpected error retrieving the file you uploaded. '
                 'Please try again and contact support if the problem persists.')
    elif isinstance(e, ImporterExcelFileEncrypted):
        return _('The file you want to import is password protected. '
                 'Please choose a file that is not password protected.')
    elif isinstance(e, ImporterExcelError):
        return _("The file uploaded has the following error: {}").format(str(e))
    elif isinstance(e, ImporterRawError):
        return str(e)
    else:
        return _("Error: {}").format(str(e))


def exit_celery_with_error_message(task, error_message):
    """
    Call this function and return the value from within a celery task to abort

    with an error message that gets passed on in a way that case importer
    will pick up and display.

    Currently it doesn't return anything and does all its magic by manually
    setting task metadata and raising Ignore,
    but the internals could change to do this through a return value instead.
    """
    update_task_state(task, states.FAILURE, get_interned_exception(error_message))
    raise Ignore()


@memoized
def get_interned_exception(message):
    """
    In tests, it's important that the error message is exactly the same object.
    """
    return Exception(message)


def merge_dicts(dict_list, keys_to_exclude):
    """
    Merges the values from two or more dicts together into a single dict.

    :param keys_to_exclude: Dict keys to not merge into the final result.

    Below is a given example. When calling the function with the following params:
    merge_dicts([
        {'one': 1, 'two': 'two'},
        {'one': 1, 'two': 'two', 'three': [3]},
        {'three': [3]},
        {'four': 'four'}],
        keys_to_exclude='four')

    This will output a result as follows:
    {'one': 2, 'two': 'twotwo', 'three': [3, 3]}
    """

    result = {}
    for d in dict_list:
        for key, value in d.items():
            if key in keys_to_exclude:
                continue

            if key in result:
                result[key] += value
            else:
                result[key] = value
    return result
