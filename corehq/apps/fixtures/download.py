import io
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import zip_longest

from django.template.defaultfilters import yesno
from django.utils.translation import gettext as _

from couchexport.export import export_raw
from couchexport.models import Format
from dimagi.utils.couch.database import iter_docs
from soil import DownloadBase
from soil.util import expose_cached_download

from corehq.apps.fixtures.exceptions import FixtureDownloadError
from corehq.apps.fixtures.models import (
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
    OwnerType,
)
from corehq.apps.fixtures.upload import DELETE_HEADER
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser


def prepare_fixture_download(table_ids, domain, task, download_id, owner_id):
    """Prepare fixture data for Excel download
    """
    data_types_book, excel_sheets = _prepare_fixture(table_ids, domain, task=task)

    header_groups = [("types", excel_sheets["types"]["headers"])]
    value_groups = [("types", excel_sheets["types"]["rows"])]
    for data_type in data_types_book:
        header_groups.append((data_type.tag, excel_sheets[data_type.tag]["headers"]))
        value_groups.append((data_type.tag, excel_sheets[data_type.tag]["rows"]))

    file = io.BytesIO()
    format = Format.XLS_2007
    export_raw(tuple(header_groups), tuple(value_groups), file, format)
    return expose_cached_download(
        file.getvalue(),
        60 * 60 * 2,
        file_extension=".xlsx",
        mimetype=Format.from_format(format).mimetype,
        content_disposition='attachment; filename="%s_lookup-tables.xlsx"' % domain,
        download_id=download_id,
        owner_ids=[owner_id],
    )


def prepare_fixture_html(table_ids, domain):
    """Prepare fixture data for HTML view
    """
    return _prepare_fixture(table_ids, domain, html_response=True)[1]


def _prepare_fixture(table_ids, domain, html_response=False, task=None):
    # HELPME
    #
    # This method has been flagged for refactoring due to its complexity and
    # frequency of touches in changesets
    #
    # If you are writing code that touches this method, your changeset
    # should leave the method better than you found it.
    #
    # Please remove this flag when this method no longer triggers an 'E' or 'F'
    # classification from the radon code static analysis

    data_types_view = _generate_data_types_view(table_ids, domain, html_response)
    total_tables = len(data_types_view)
    # when total_tables < 4 the final percentage can be >= 100%, but for
    # a small number of tables it renders more accurate progress
    total_events = (total_tables + (0 if total_tables < 4 else 1)) * 10

    now = datetime.utcnow
    last_update = [now()]
    update_period = timedelta(seconds=1)  # do not update progress more than once a second

    def _update_progress(event_count, item_count, items_in_table):
        if task and now() - last_update[0] > update_period:
            last_update[0] = now()
            processed = event_count * 10 + (10 * item_count / items_in_table)
            processed = min(processed, total_events)  # limit at 100%
            DownloadBase.set_progress(task, processed, total_events)

    # book-keeping data from view_results for repeated use
    data_types_book = []
    data_items_book_by_type = {}
    item_helpers_by_type = {}
    """
        Contains all excel sheets in following format
        excel_sheets = {
            "types": {
                "headers": [],
                "rows": [(row), (row), (row)]
            }
            "next-sheet": {
                "headers": [],
                "rows": [(row), (row), (row)]
            },
            ...
        }
    """
    excel_sheets = {}

    def get_field_prop_format(field_number, property_number):
        return f"field {field_number} : property {property_number}"

    def empty_padding_list(length):
        return [""] * length

    max_fields = 0
    max_item_attributes = 0
    """
        - Helper to generate headers like "field 2: property 1"
        - Captures max_num_of_properties for any field of any type at the list-index.
        Example values:
            [0, 1] -> "field 2: property 1" (first-field has zero-props, second has 1 property)
            [1, 1] -> "field 1: property 1" (first-field has 1 property, second has 1 property)
            [0, 2] -> "field 2: property 1", "field 2: property 2"
    """
    field_prop_count = []
    """
        captures all possible 'field-property' values for each data-type
        Example value
          {
            u'clinics': {'field 2 : property 1': u'lang'},
            u'growth_chart': {'field 2 : property 2': u'maxWeight'}
          }
    """
    owner_names = OwnerNames(data_types_view)
    type_field_properties = {}
    for event_count, data_type in enumerate(data_types_view):
        # Helpers to generate 'types' sheet
        type_field_properties[data_type.tag] = {}
        data_types_book.append(data_type)
        if len(data_type.fields) > max_fields:
            max_fields = len(data_type.fields)
        if len(data_type.item_attributes) > max_item_attributes:
            max_item_attributes = len(data_type.item_attributes)
        for index, field in enumerate(data_type.fields):
            if len(field_prop_count) <= index:
                field_prop_count.append(len(field.properties))
            elif field_prop_count[index] <= len(field.properties):
                field_prop_count[index] = len(field.properties)
            if len(field.properties) > 0:
                for prop_index, property in enumerate(field.properties):
                    prop_key = get_field_prop_format(index + 1, prop_index + 1)
                    type_field_properties[data_type.tag][prop_key] = property

        # Helpers to generate item-sheets
        data_items_book_by_type[data_type.tag] = []
        max_users = 0
        max_groups = 0
        max_locations = 0
        max_field_prop_combos = {field.name: 0 for field in data_type.fields}
        fixture_data = LookupTableRow.objects.iter_rows(domain, table_id=data_type.id)
        num_rows = LookupTableRow.objects.filter(domain=domain, table_id=data_type.id).count()
        for n, item_row in enumerate(fixture_data):
            _update_progress(event_count, n, num_rows)
            data_items_book_by_type[data_type.tag].append(item_row)
            max_groups = max(max_groups, owner_names.count(item_row, OwnerType.Group))
            max_users = max(max_users, owner_names.count(item_row, OwnerType.User))
            max_locations = max(max_locations, owner_names.count(item_row, OwnerType.Location))
            for field_key in item_row.fields:
                if field_key in max_field_prop_combos:
                    max_field_prop_combos[field_key] = max(
                        max_field_prop_combos[field_key],
                        len(item_row.fields[field_key]),
                    )

        item_helpers = {
            "max_users": max_users,
            "max_groups": max_groups,
            "max_locations": max_locations,
            "max_field_prop_combos": max_field_prop_combos,
        }
        item_helpers_by_type[data_type.tag] = item_helpers

    # Prepare 'types' sheet data
    indexed_field_numbers = get_indexed_field_numbers(data_types_view)
    types_sheet = {"headers": [], "rows": []}
    types_sheet["headers"] = [DELETE_HEADER, "table_id", 'is_global?']
    types_sheet["headers"].extend(iter_types_headers(max_fields, indexed_field_numbers))
    types_sheet["headers"].extend(["property %d" % x for x in range(1, max_item_attributes + 1)])
    field_prop_headers = []
    for field_num, prop_num in enumerate(field_prop_count):
        if prop_num > 0:
            for c in range(0, prop_num):
                prop_key = get_field_prop_format(field_num + 1, c + 1)
                field_prop_headers.append(prop_key)
                types_sheet["headers"].append(prop_key)

    for data_type in data_types_book:
        common_vals = ["N", data_type.tag, yesno(data_type.is_global)]
        field_vals = []
        # Count "is_indexed?" columns added, because data types with fewer fields will add fewer columns
        indexed_field_count = 0
        for i, field in enumerate(data_type.fields):
            field_vals.append(field.field_name)
            if i in indexed_field_numbers:
                field_vals.append('yes' if field.is_indexed else 'no')
                indexed_field_count += 1
        field_vals.extend(empty_padding_list(
            max_fields - len(data_type.fields)
            + len(indexed_field_numbers) - indexed_field_count
        ))
        item_att_vals = (data_type.item_attributes + empty_padding_list(
            max_item_attributes - len(data_type.item_attributes)
        ))
        prop_vals = []
        if data_type.tag in type_field_properties:
            props = type_field_properties.get(data_type.tag)
            prop_vals.extend([props.get(key, "") for key in field_prop_headers])
        row = tuple(common_vals[2 if html_response else 0:] + field_vals + item_att_vals + prop_vals)
        types_sheet["rows"].append(row)

    types_sheet["rows"] = tuple(types_sheet["rows"])
    types_sheet["headers"] = tuple(types_sheet["headers"])
    excel_sheets["types"] = types_sheet

    # Prepare 'items' sheet data for each data-type
    for n, data_type in enumerate(data_types_book):
        _update_progress(total_tables, n, total_tables)
        item_sheet = {"headers": [], "rows": []}
        item_helpers = item_helpers_by_type[data_type.tag]
        max_users = item_helpers["max_users"]
        max_groups = item_helpers["max_groups"]
        max_locations = item_helpers["max_locations"]
        max_field_prop_combos = item_helpers["max_field_prop_combos"]
        common_headers = ["UID", DELETE_HEADER]
        user_headers = ["user %d" % x for x in range(1, max_users + 1)]
        group_headers = ["group %d" % x for x in range(1, max_groups + 1)]
        location_headers = ["location %d" % x for x in range(1, max_locations + 1)]
        field_headers = []
        item_att_headers = ["property: " + attribute for attribute in data_type.item_attributes]
        for field in data_type.fields:
            if len(field.properties) == 0:
                field_headers.append("field: " + field.field_name)
            else:
                prop_headers = []
                for x in range(1, max_field_prop_combos[field.field_name] + 1):
                    for property in field.properties:
                        prop_headers.append("%(name)s: %(prop)s %(count)s" % {
                            "name": field.field_name,
                            "prop": property,
                            "count": x
                        })
                    prop_headers.append("field: %(name)s %(count)s" % {
                        "name": field.field_name,
                        "count": x
                    })
                field_headers.extend(prop_headers)
        item_sheet["headers"] = tuple(
            common_headers[2 if html_response else 0:]
            + field_headers
            + item_att_headers
            + user_headers
            + group_headers
            + location_headers
        )
        excel_sheets[data_type.tag] = item_sheet
        for item_row in data_items_book_by_type[data_type.tag]:
            common_vals = [str(item_row.id.hex), "N"]
            users = owner_names.get_usernames(item_row)
            groups = owner_names.get_group_names(item_row)
            locations = owner_names.get_location_codes(item_row)
            user_vals = (users + empty_padding_list(max_users - len(users)))
            group_vals = (groups + empty_padding_list(max_groups - len(groups)))
            location_vals = (locations + empty_padding_list(max_locations - len(locations)))
            field_vals = []
            item_att_vals = [item_row.item_attributes[attribute] for attribute in data_type.item_attributes]
            for field in data_type.fields:
                if len(field.properties) == 0:
                    field_values = item_row.fields[field.name]
                    value = field_values[0].value if field_values else ""
                    field_vals.append(value)
                else:
                    field_prop_vals = []
                    cur_combo_count = len(item_row.fields[field.name])
                    cur_prop_count = len(field.properties)
                    for field_prop_combo in item_row.fields[field.name]:
                        for property in field.properties:
                            field_prop_vals.append(field_prop_combo.properties.get(property, None) or "")
                        field_prop_vals.append(field_prop_combo.value)
                    padding_list_len = ((max_field_prop_combos[field.name] - cur_combo_count)
                                        * (cur_prop_count + 1))
                    field_prop_vals.extend(empty_padding_list(padding_list_len))
                    field_vals.extend(field_prop_vals)
            row = tuple(
                common_vals[2 if html_response else 0:]
                + field_vals
                + item_att_vals
                + user_vals
                + group_vals
                + location_vals
            )
            item_sheet["rows"].append(row)
        item_sheet["rows"] = tuple(item_sheet["rows"])
        excel_sheets[data_type.tag] = item_sheet

    return data_types_book, excel_sheets


def _generate_data_types_view(table_ids, domain, html_response):
    if table_ids and table_ids[0]:
        try:
            data_types_view = [LookupTable.objects.get(id=id, domain=domain) for id in table_ids]
        except LookupTable.DoesNotExist:
            if html_response:
                raise FixtureDownloadError(
                    _("Sorry, we couldn't find that table. If you think this "
                      "is a mistake please report an issue."))
            data_types_view = LookupTable.objects.by_domain(domain)
    else:
        data_types_view = LookupTable.objects.by_domain(domain)

    if html_response:
        return list(data_types_view)[0:1]
    else:
        return list(data_types_view)


class OwnerNames:

    def __init__(self, tables):
        # owners = {row_id: {owner_type: owner_ids_set, ...}, ...}
        self.owners = owners = defaultdict(lambda: defaultdict(set))
        row_owners = LookupTableRowOwner.objects.filter(
            row__table_id__in=[t.id for t in tables]
        ).values_list("row_id", "owner_type", "owner_id", named=True)
        for rec in row_owners:
            owners[rec.row_id][rec.owner_type].add(rec.owner_id)
        self.names = {
            OwnerType.User: self._load_usernames(owners),
            OwnerType.Group: self._load_group_names(owners),
            OwnerType.Location: self._load_location_codes(owners),
        }

    def _load_usernames(self, owners):
        docs = self._iter_couch_docs(owners, OwnerType.User, CommCareUser)
        return {u._id: u.raw_username for u in docs}

    def _load_group_names(self, owners):
        docs = self._iter_couch_docs(owners, OwnerType.Group, Group)
        return {g._id: g.name for g in docs}

    def _iter_couch_docs(self, owners, owner_type, couch_model):
        doc_ids = {id for ids in owners.values() for id in ids[owner_type]}
        if doc_ids:
            db = couch_model.get_db()
            yield from (couch_model.wrap(g) for g in iter_docs(db, doc_ids))

    def _load_location_codes(self, owners):
        loc_ids = {id for ids in owners.values() for id in ids[OwnerType.Location]}
        if not loc_ids:
            return {}
        codes = SQLLocation.objects.filter(
            location_id__in=list(loc_ids)).values_list("location_id", "site_code")
        return dict(codes)

    def count(self, row, owner_type):
        names = self.names[owner_type]
        return sum(1 for doc_id in self.owners[row.id][owner_type] if doc_id in names)

    def get_usernames(self, row):
        user_ids = self.owners[row.id][OwnerType.User]
        names = self.names[OwnerType.User]
        return sorted(names[doc_id] for doc_id in user_ids if doc_id in names)

    def get_group_names(self, row):
        group_ids = self.owners[row.id][OwnerType.Group]
        names = self.names[OwnerType.Group]
        return sorted(names[doc_id] for doc_id in group_ids if doc_id in names)

    def get_location_codes(self, row):
        loc_ids = self.owners[row.id][OwnerType.Location]
        names = self.names[OwnerType.Location]
        return sorted(names[loc_id] for loc_id in loc_ids if loc_id in names)


def get_indexed_field_numbers(tables):
    class no_index:
        is_indexed = False
    field_lists = zip_longest(*(t.fields for t in tables), fillvalue=no_index)
    return {i for i, fields in enumerate(field_lists) if any(f.is_indexed for f in fields)}


def iter_types_headers(max_fields, indexed_field_numbers):
    for i in range(max_fields):
        yield f"field {i + 1}"
        if i in indexed_field_numbers:
            yield f"field {i + 1}: is_indexed?"
