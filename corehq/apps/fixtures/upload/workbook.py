from weakref import WeakKeyDictionary

from django.utils.translation import gettext as _, gettext_lazy

from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload.const import DELETE_HEADER, INVALID, MULTIPLE
from corehq.apps.fixtures.upload.failure_messages import FAILURE_MESSAGES
from corehq.apps.fixtures.utils import is_identifier_invalid
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
)
from corehq.util.workbook_json.excel import (
    JSONReaderError,
    get_workbook as excel_get_workbook
)

from ..models import (
    Field,
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
    TypeField,
)


def get_workbook(file_or_filename):
    return _FixtureWorkbook(file_or_filename)


class _FixtureWorkbook(object):
    """
    Helper class for working with the fixture workbook
    """

    def __init__(self, file_or_filename):
        try:
            self.workbook = excel_get_workbook(file_or_filename)
        except WorkbookJSONError as e:
            raise FixtureUploadError([str(e)])
        self._rows = {}
        self.item_keys = WeakKeyDictionary()
        self.ownership = WeakKeyDictionary()

    def get_types_sheet(self):
        try:
            return self.get_data_sheet("types")
        except WorksheetNotFound:
            raise FixtureUploadError([FAILURE_MESSAGES['no_types_sheet']])
        except JSONReaderError as e:
            raise FixtureUploadError(e.args)

    def get_data_sheet(self, tag):
        # Cache all rows in memory in order to traverse them more than
        # once because IteratorJSONReader only allows a single iteration
        # and openpyxl's ReadOnlyWorksheet does not have an efficient
        # means of traversing sheets more than once.
        try:
            rows = self._rows[tag]
        except KeyError:
            rows = self._rows[tag] = list(self.workbook.get_worksheet(tag))
        return rows

    def get_all_type_sheets(self):
        type_sheets = []
        seen_tags = set()
        for dt in self.get_types_sheet():
            table_definition = _FixtureTableDefinition.from_row(dt)
            if table_definition.table_id in seen_tags:
                raise FixtureUploadError([
                    _(FAILURE_MESSAGES['duplicate_tag'])
                    .format(tag=table_definition.table_id)])

            seen_tags.add(table_definition.table_id)
            type_sheets.append(table_definition)
        return type_sheets

    def get_owners(self):
        """Get dict of user, group, and location names in this workbook

        Result:
        ```py
        {
            "user": {"user1", "user2", ...},
            "group": {"group1", "group2", ...},
            "location": {"location1", "location2", ...},
        }
        ```
        """
        owners = {
            "user": set(),
            "group": set(),
            "location": set(),
        }
        transforms = {
            "user": str.lower,
            "group": lambda x: x,
            "location": str.lower,
        }
        for tabledef in self.get_all_type_sheets():
            for key, values in owners.items():
                rows = self.get_data_sheet(tabledef.table_id)
                transform = transforms[key]
                values.update(
                    transform(str(name))
                    for row in rows
                    if key in row
                    for name in row[key]
                )
        return owners

    def count_tables(self):
        return len(self.get_all_type_sheets())

    def count_rows(self, data_type):
        return len(self.get_data_sheet(data_type.tag))

    def iter_tables(self, domain):
        for sheet in self.get_all_type_sheets():
            if sheet.delete:
                yield Deleted(sheet.table_id)
                continue
            table = LookupTable(
                domain=domain,
                tag=sheet.table_id,
                is_global=sheet.is_global,
                fields=sheet.fields,
                item_attributes=sheet.item_attributes,
            )
            self.item_keys[table] = sheet.table_id
            yield table

    def iter_rows(self, data_type, sort_keys):
        type_fields = data_type.fields
        sort_key = -1
        for i, di in enumerate(self.get_data_sheet(data_type.tag)):
            uid = di.get('UID')
            if _is_deleted(di):
                if uid:
                    yield Deleted(uid)
                continue
            sort_key = max(sort_keys.get(uid, i), sort_key + 1)
            item = LookupTableRow(
                domain=data_type.domain,
                table_id=data_type.id,
                fields={
                    field.name: _process_item_field(field, di)
                    for field in type_fields
                },
                item_attributes=di.get('property', {}),
                sort_key=sort_key,
            )
            if uid:
                self.item_keys[item] = uid
            self.ownership[item] = ownership = {}
            for owner_type in ["user", "group", "location"]:
                owner_names = di.get(owner_type)
                if owner_names:
                    if owner_type == "group":
                        owner_names = [str(n) for n in owner_names]
                    else:
                        # names, except for groups, are case insensitive
                        owner_names = [str(n).lower() for n in owner_names]
                    ownership[owner_type] = owner_names
            yield item

    def get_key(self, obj):
        if isinstance(obj, LookupTableRowOwner):
            return None
        return self.item_keys.get(obj)

    def iter_ownerships(self, row, row_id, owner_ids_map, errors):
        ownerships = self.ownership[row]
        if not ownerships:
            return
        for owner_type, names in ownerships.items():
            for name in names:
                owner_id = owner_ids_map[owner_type].get(name)
                if owner_id is None or owner_id is MULTIPLE or owner_id is INVALID:
                    key = (owner_id, owner_type)
                    errors.append(self.ownership_errors[key] % {'name': name})
                    continue
                yield LookupTableRowOwner(
                    domain=row.domain,
                    row_id=row_id,
                    owner_type=OwnerType.from_string(owner_type),
                    owner_id=owner_id,
                )

    ownership_errors = {
        (None, "user"): gettext_lazy("Unknown user: '%(name)s'. But the row is successfully added"),
        (None, "group"): gettext_lazy("Unknown group: '%(name)s'. But the row is successfully added"),
        (None, "location"): gettext_lazy("Unknown location: '%(name)s'. But the row is successfully added"),
        (INVALID, "user"): gettext_lazy("Invalid username: '%(name)s'. But the row is successfully added"),
        (MULTIPLE, "location"): gettext_lazy(
            "Multiple locations found with the name: '%(name)s'.  "
            "Try using site code. But the row is successfully added"
        ),
    }


class Deleted:
    def __init__(self, key):
        self.key = key


class _FixtureTableDefinition(object):

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
        if is_identifier_invalid(tag):
            raise FixtureUploadError([
                _(FAILURE_MESSAGES['invalid_table_id']).format(tag=tag)
            ])

        field_names = row_dict.get('field')
        item_attributes = row_dict.get('property')

        if field_names is None and item_attributes is None:
            raise FixtureUploadError([_(FAILURE_MESSAGES['neither_fields_nor_attributes']).format(tag=tag)])

        field_names = [] if field_names is None else field_names
        item_attributes = [] if item_attributes is None else item_attributes

        def _get_field_properties(prop_key):
            properties = []
            if prop_key in row_dict and 'property' in row_dict[prop_key]:
                properties = row_dict[prop_key]["property"]
                if not isinstance(properties, list):
                    error_message = _(FAILURE_MESSAGES["wrong_property_syntax"]).format(
                        prop_key=prop_key,
                    )
                    raise FixtureUploadError([error_message])
            return properties

        def _get_field_is_indexed(prop_key):
            is_indexed = False
            if prop_key in row_dict and 'is_indexed' in row_dict[prop_key]:
                is_indexed = row_dict[prop_key]["is_indexed"]
                if not isinstance(is_indexed, bool):
                    error_message = _(FAILURE_MESSAGES["wrong_index_syntax"]).format(
                        prop_key=prop_key,
                    )
                    raise FixtureUploadError([error_message])
            return is_indexed

        def is_number(text):
            text = str(text)
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
            TypeField(
                name=field,
                properties=_get_field_properties(f'field {i + 1}'),
                is_indexed=_get_field_is_indexed(f'field {i + 1}'),
            ) for i, field in enumerate(field_names)
        ]

        return cls(
            table_id=tag,
            fields=fields,
            item_attributes=item_attributes,
            is_global=row_dict.get('is_global', False),
            uid=row_dict.get('UID'),
            delete=_is_deleted(row_dict),
        )


def _is_deleted(row_dict):
    return (row_dict.get(DELETE_HEADER) or '').lower() == 'y'


def _process_item_field(field, data_item):
    """Processes field_list of a data item from fields in the uploaded excel sheet.

    Returns FieldList
    """
    if not field.properties:
        return [Field(
            # str to cast ints and multi-language strings
            value=str(data_item['field'][field.name]),
            properties={}
        )]

    field_list = []
    field_prop_combos = data_item['field'][field.name]
    prop_combo_len = len(field_prop_combos)
    prop_dict = data_item[field.name]
    for x in range(0, prop_combo_len):
        fix_item_field = Field(
            value=str(field_prop_combos[x]),
            properties={prop: str(prop_dict[prop][x]) for prop in prop_dict}
        )
        field_list.append(fix_item_field)
    return field_list
