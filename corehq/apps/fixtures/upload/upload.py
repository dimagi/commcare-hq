from collections import namedtuple
import re
from django.template.loader import render_to_string

from django.utils.translation import ugettext as _, ugettext_noop

from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.models import FixtureTypeField
from corehq.util.spreadsheets.excel import WorksheetNotFound, \
    WorkbookJSONReader, JSONReaderError, HeaderValueError, InvalidExcelFileException
from corehq.apps.locations.models import SQLLocation


DELETE_HEADER = "Delete(Y/N)"
FAILURE_MESSAGES = {
    "has_no_column": ugettext_noop(
        "Workbook 'types' has no column '{column_name}'."
    ),
    "neither_fields_nor_attributes": ugettext_noop(
        "Lookup-tables can not have empty fields and empty properties on items. "
        "table_id '{tag}' has no fields and no properties"
    ),
    "duplicate_tag": ugettext_noop(
        "Lookup-tables should have unique 'table_id'. "
        "There are two rows with table_id '{tag}' in 'types' sheet."
    ),
    "has_no_field_column": ugettext_noop(
        "Excel-sheet '{tag}' does not contain the column 'field: {field}' "
        "as specified in its 'types' definition"
    ),
    "has_extra_column": ugettext_noop(
        "Excel-sheet '{tag}' has an extra column"
        "'field: {field}' that's not defined in its 'types' definition"
    ),
    "wrong_property_syntax": ugettext_noop(
        "Properties should be specified as 'field 1: property 1'. In 'types' sheet, "
        "'{prop_key}' is not correctly formatted"
    ),
    "invalid_field_name_numerical": ugettext_noop(
        "Error in 'types' sheet for 'field {i}', '{val}'. "
        "Field names should be strings, not numbers"
    ),
    "invalid_field_syntax": ugettext_noop(
        "In excel-sheet '{tag}', field '{field}' should be numbered as 'field: {field} integer",
    ),
    "sheet_has_no_property": ugettext_noop(
        "Excel-sheet '{tag}' does not contain property "
        "'{property}' of the field '{field}' as specified in its 'types' definition"
    ),
    "sheet_has_extra_property": ugettext_noop(
        "Excel-sheet '{tag}' has an extra property "
        "'{property}' for the field '{field}' that's not defined in its 'types' definition. "
        "Re-check the formatting"
    ),
    "invalid_field_with_property": ugettext_noop(
        "Fields with attributes should be numbered as 'field: {field} integer'"
    ),
    "invalid_property": ugettext_noop(
        "Attribute should be written as '{field}: {prop} integer'"
    ),
    "wrong_field_property_combos": ugettext_noop(
        "Number of values for field '{field}' and attribute '{prop}' should be same"
    ),
    "type_has_no_sheet": ugettext_noop(
        "There's no sheet for type '{type}' in 'types' sheet. "
        "There must be one sheet per row in the 'types' sheet.",
    ),
}


class FixtureUploadResult(object):
    """
    Helper structure for handling the results of a fixture upload.
    """

    def __init__(self):
        self.success = True
        self.messages = []
        self.errors = []
        self.number_of_fixtures = 0

    def get_display_message(self):
        message = render_to_string('fixtures/partials/fixture_upload_status_api.txt', {
            'result': self,
        })
        message = u'\n'.join(re.split(r'\n*', message)).strip()
        return message


class FixtureTableDefinition(object):

    def __init__(self, table_id, fields, item_attributes, is_global, uid, delete):
        self.table_id = table_id
        self.fields = fields
        self.item_attributes = item_attributes
        self.is_global = is_global
        self.uid = uid
        self.delete = delete

    @classmethod
    def from_row(cls, row_dict):
        tag = row_dict.get('table_id') or row_dict.get('tag')
        if tag is None:
            raise FixtureUploadError([
                _(FAILURE_MESSAGES['has_no_column']).format(column_name='table_id')])

        field_names = row_dict.get('field')
        item_attributes = row_dict.get('property')

        if field_names is None and item_attributes is None:
            raise FixtureUploadError([_(FAILURE_MESSAGES['neither_fields_nor_attributes']).format(tag=tag)])

        field_names = [] if field_names is None else field_names
        item_attributes = [] if item_attributes is None else item_attributes

        def _get_field_properties(prop_key):
            if prop_key in row_dict:
                try:
                    properties = row_dict[prop_key]["property"]
                    assert isinstance(properties, list)
                except (KeyError, AssertionError):
                    error_message = _(FAILURE_MESSAGES["wrong_property_syntax"]).format(
                        prop_key=prop_key,
                    )
                    raise FixtureUploadError([error_message])
                else:
                    return properties
            else:
                return []

        def is_number(text):
            text = unicode(text)
            try:
                float(text)
                return True
            except ValueError:
                return False

        for i, field_name in enumerate(field_names):
            if is_number(field_name):
                message = _(FAILURE_MESSAGES['invalid_field_name_numerical']).format(
                    i=i + 1,
                    val=field_name,
                )
                raise FixtureUploadError([message])

        fields = [
            FixtureTypeField(
                field_name=field,
                properties=_get_field_properties('field {count}'.format(count=i + 1))
            ) for i, field in enumerate(field_names)
        ]

        return FixtureTableDefinition(
            table_id=tag,
            fields=fields,
            item_attributes=item_attributes,
            is_global=row_dict.get('is_global', False),
            uid=row_dict.get('UID'),
            delete=(row_dict.get(DELETE_HEADER) or '').lower() == 'y',
        )


class FixtureWorkbook(object):
    """
    Helper class for working with the fixture workbook
    """

    def __init__(self, file_or_filename):
        try:
            self.workbook = WorkbookJSONReader(file_or_filename)
        except AttributeError:
            raise FixtureUploadError([_("Error processing your Excel (.xlsx) file")])
        except InvalidExcelFileException:
            raise FixtureUploadError([_("Invalid file-format. Please upload a valid xlsx file.")])
        except HeaderValueError as e:
            raise FixtureUploadError([unicode(e)])
        except JSONReaderError as e:
            raise FixtureUploadError([unicode(e)])

    def get_types_sheet(self):
        try:
            return self.workbook.get_worksheet(title='types')
        except WorksheetNotFound as e:
            raise FixtureUploadError([
                _("Workbook does not contain a sheet called '%(title)s'")
                % {'title': e.title}])

    def get_data_sheet(self, data_type_tag):
        return self.workbook.get_worksheet(data_type_tag)

    def get_all_type_sheets(self):
        type_sheets = []
        seen_tags = set()
        for number_of_fixtures, dt in enumerate(self.get_types_sheet()):
            table_definition = FixtureTableDefinition.from_row(dt)
            if table_definition.table_id in seen_tags:
                raise FixtureUploadError([
                    _(FAILURE_MESSAGES['duplicate_tag'])
                    .format(tag=table_definition.table_id)])

            seen_tags.add(table_definition.table_id)
            type_sheets.append(table_definition)
        return type_sheets

    def validate(self):
        from corehq.apps.fixtures.upload.run_upload import validate_fixture_upload
        self.get_types_sheet()
        error_messages = validate_fixture_upload(self)
        if error_messages:
            raise FixtureUploadError(error_messages)


def validate_fixture_file_format(file_or_filename):
    """
    Does basic validation on the uploaded file. Raises a FixtureUploadError if
    something goes wrong.
    """
    workbook = FixtureWorkbook(file_or_filename)
    workbook.validate()


def get_workbook(file_or_filename):
    return FixtureWorkbook(file_or_filename)


LocationCache = namedtuple("LocationCache", "is_error location message")


def get_memoized_location(domain):
    """
    Returns a memoized location getter containing error information.
    """
    locations = {}

    def get_location(user_input):
        user_input = user_input.lower()
        if user_input not in locations:
            try:
                loc = SQLLocation.objects.get_from_user_input(domain, user_input)
                locations[user_input] = LocationCache(False, loc, None)
            except SQLLocation.DoesNotExist:
                locations[user_input] = LocationCache(True, None, _(
                    "Unknown location: '%(name)s'. But the row is "
                    "successfully added"
                ) % {'name': user_input})
            except SQLLocation.MultipleObjectsReturned:
                locations[user_input] = LocationCache(True, None, _(
                    "Multiple locations found with the name: '%(name)s'.  "
                    "Try using site code. But the row is successfully added"
                ) % {'name': user_input})
        return locations[user_input]
    return get_location
