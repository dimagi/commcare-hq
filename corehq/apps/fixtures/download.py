from cStringIO import StringIO
from couchdbkit import ResourceNotFound
from datetime import datetime, timedelta

from django.template.defaultfilters import yesno
from django.utils.translation import ugettext as _

from corehq.apps.fixtures.exceptions import FixtureDownloadError
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc
from corehq.apps.fixtures.upload import DELETE_HEADER
from couchexport.export import export_raw
from couchexport.models import Format

from soil import DownloadBase
from soil.util import expose_cached_download


def prepare_fixture_download(table_ids, domain, task, download_id):
    """Prepare fixture data for Excel download
    """
    data_types_book, excel_sheets = _prepare_fixture(table_ids, domain, task=task)

    header_groups = [("types", excel_sheets["types"]["headers"])]
    value_groups = [("types", excel_sheets["types"]["rows"])]
    for data_type in data_types_book:
        header_groups.append((data_type.tag, excel_sheets[data_type.tag]["headers"]))
        value_groups.append((data_type.tag, excel_sheets[data_type.tag]["rows"]))

    file = StringIO()
    format = Format.XLS_2007
    export_raw(tuple(header_groups), tuple(value_groups), file, format)
    return expose_cached_download(
        file.getvalue(),
        60 * 60 * 2,
        file_extension=".xlsx",
        mimetype=Format.from_format(format).mimetype,
        content_disposition='attachment; filename="%s_fixtures.xlsx"' % domain,
        download_id=download_id,
    )


def prepare_fixture_html(table_ids, domain):
    """Prepare fixture data for HTML view
    """
    return _prepare_fixture(table_ids, domain, html_response=True)[1]


def _prepare_fixture(table_ids, domain, html_response=False, task=None):
    if table_ids and table_ids[0]:
        try:
            data_types_view = [FixtureDataType.get(id) for id in table_ids]
        except ResourceNotFound:
            if html_response:
                raise FixtureDownloadError(
                    _("Sorry, we couldn't find that table. If you think this "
                      "is a mistake please report an issue."))
            data_types_view = FixtureDataType.by_domain(domain)
    else:
        data_types_view = FixtureDataType.by_domain(domain)

    if html_response:
        data_types_view = list(data_types_view)[0:1]

    total_tables = len(data_types_view)
    # when total_tables < 4 the final percentage can be >= 100%, but for
    # a small number of tables it renders more accurate progress
    total_events = (total_tables + (0 if total_tables < 4 else 1)) * 10

    now = datetime.utcnow
    last_update = [now()]
    upate_period = timedelta(seconds=1)  # do not update progress more than once a second

    def _update_progress(event_count, item_count, items_in_table):
        if task and now() - last_update[0] > upate_period:
            last_update[0] = now()
            processed = event_count * 10 + (10. * item_count / items_in_table)
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

    def empty_padding_list(length):
        return ["" for x in range(0, length)]

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
    type_field_properties = {}
    get_field_prop_format = lambda x, y: "field " + str(x) + " : property " + str(y)
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
        max_field_prop_combos = {field_name: 0 for field_name in data_type.fields_without_attributes}
        fixture_data = FixtureDataItem.by_data_type(domain, data_type.get_id)
        num_rows = len(fixture_data)
        for n, item_row in enumerate(fixture_data):
            _update_progress(event_count, n, num_rows)
            data_items_book_by_type[data_type.tag].append(item_row)
            max_groups = max(max_groups, len(item_row.groups))
            max_users = max(max_users, len(item_row.users))
            max_locations = max(max_locations, len(item_row.locations))
            for field_key in item_row.fields:
                if field_key in max_field_prop_combos:
                    max_combos = max_field_prop_combos[field_key]
                    cur_combo_len = len(item_row.fields[field_key].field_list)
                    max_combos = cur_combo_len if cur_combo_len > max_combos else max_combos
                    max_field_prop_combos[field_key] = max_combos

        item_helpers = {
            "max_users": max_users,
            "max_groups": max_groups,
            "max_locations": max_locations,
            "max_field_prop_combos": max_field_prop_combos,
        }
        item_helpers_by_type[data_type.tag] = item_helpers

    # Prepare 'types' sheet data
    types_sheet = {"headers": [], "rows": []}
    types_sheet["headers"] = [DELETE_HEADER, "table_id", 'is_global?']
    types_sheet["headers"].extend(["field %d" % x for x in range(1, max_fields + 1)])
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
        field_vals = ([field.field_name for field in data_type.fields]
                      + empty_padding_list(max_fields - len(data_type.fields)))
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
            common_vals = [str(_id_from_doc(item_row)), "N"]
            user_vals = ([user.raw_username for user in item_row.users]
                         + empty_padding_list(max_users - len(item_row.users)))
            group_vals = ([group.name for group in item_row.groups]
                          + empty_padding_list(max_groups - len(item_row.groups)))
            location_vals = ([loc.site_code for loc in item_row.locations]
                             + empty_padding_list(max_groups - len(item_row.locations)))
            field_vals = []
            item_att_vals = [item_row.item_attributes[attribute] for attribute in data_type.item_attributes]
            for field in data_type.fields:
                if len(field.properties) == 0:
                    fixture_fields = item_row.fields.get(field.field_name)
                    if fixture_fields and any(fixture_fields.field_list):
                        value = item_row.fields.get(field.field_name).field_list[0].field_value
                    else:
                        value = ""
                    field_vals.append(value)
                else:
                    field_prop_vals = []
                    cur_combo_count = len(item_row.fields.get(field.field_name).field_list)
                    cur_prop_count = len(field.properties)
                    for count, field_prop_combo in enumerate(item_row.fields.get(field.field_name).field_list):
                        for property in field.properties:
                            field_prop_vals.append(field_prop_combo.properties.get(property, None) or "")
                        field_prop_vals.append(field_prop_combo.field_value)
                    padding_list_len = ((max_field_prop_combos[field.field_name] - cur_combo_count)
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
