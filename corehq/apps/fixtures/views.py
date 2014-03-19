import json
import os
import tempfile
from couchdbkit import ResourceNotFound

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.validators import ValidationError
from django.http import HttpResponseBadRequest, HttpResponseRedirect, Http404, HttpResponse
from django.template.defaultfilters import yesno
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView
from django.shortcuts import render
from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback

from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.fixtures.exceptions import ExcelMalformatException, FixtureAPIException, DuplicateFixtureTagException
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc, FieldList, FixtureTypeField, FixtureItemField
from corehq.apps.groups.models import Group
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.bulkupload import GroupMemoizer
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CommCareUser, Permissions
from corehq.apps.users.util import normalize_username
from couchexport.export import UnsupportedExportFormat, export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.utils.decorators.view import get_file

from copy import deepcopy
from soil import CachedDownload, DownloadBase
from soil.util import expose_download


require_can_edit_fixtures = lambda *args, **kwargs: (
    require_permission(Permissions.edit_data)(
        requires_privilege_with_fallback(privileges.LOOKUP_TABLES)(*args, **kwargs)
    )
)


def strip_json(obj, disallow_basic=None, disallow=None):
    disallow = disallow or []
    if disallow_basic is None:
        disallow_basic = ['_rev', 'domain', 'doc_type']
    disallow += disallow_basic
    ret = {}
    try:
        obj = obj.to_json()
    except Exception:
        pass
    for key in obj:
        if key not in disallow:
            ret[key] = obj[key]

    return ret

def _to_kwargs(req):
    # unicode can mix this up so have a little utility to do it
    # was seeing this only locally, not sure if python / django
    # version dependent
    return dict((str(k), v) for k, v in json.load(req).items())

@require_can_edit_fixtures
def tables(request, domain):
    if request.method == 'GET':
        return json_response([strip_json(x) for x in FixtureDataType.by_domain(domain)])

@require_can_edit_fixtures
def update_tables(request, domain, data_type_id, test_patch={}):
    """
    receives a JSON-update patch like following
    {
        "_id":"0920fe1c6d4c846e17ee33e2177b36d6",
        "tag":"growth",
        "view_link":"/a/gsid/fixtures/view_lookup_tables/?table_id:0920fe1c6d4c846e17ee33e2177b36d6",
        "is_global":false,
        "fields":{"genderr":{"update":"gender"},"grade":{}}
    }
    """
    if data_type_id:
        try:
            data_type = FixtureDataType.get(data_type_id)
        except ResourceNotFound:
            raise Http404()

        assert(data_type.doc_type == FixtureDataType._doc_type)
        assert(data_type.domain == domain)

        if request.method == 'GET':
            return json_response(strip_json(data_type))

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)
            return json_response({})
        elif not request.method == 'PUT':
            return HttpResponseBadRequest()

    if request.method == 'POST' or request.method == "PUT":
        fields_update = test_patch or _to_kwargs(request)
        fields_patches = fields_update["fields"]
        data_tag = fields_update["tag"]
        is_global = fields_update["is_global"]
        with CouchTransaction() as transaction:
            if data_type_id:
                data_type = update_types(fields_patches, domain, data_type_id, data_tag, is_global, transaction)
                update_items(fields_patches, domain, data_type_id, transaction)
            else:
                if FixtureDataType.fixture_tag_exists(domain, data_tag):
                    return HttpResponseBadRequest("DuplicateFixture")
                else:
                    data_type = create_types(fields_patches, domain, data_tag, is_global, transaction)
        return json_response(strip_json(data_type))


def update_types(patches, domain, data_type_id, data_tag, is_global, transaction):
    data_type = FixtureDataType.get(data_type_id)
    fields_patches = deepcopy(patches)
    assert(data_type.doc_type == FixtureDataType._doc_type)
    assert(data_type.domain == domain)
    old_fields = data_type.fields
    new_fixture_fields = []
    setattr(data_type, "tag", data_tag)
    setattr(data_type, "is_global", is_global)
    for old_field in old_fields:
        patch = fields_patches.pop(old_field.field_name, {})
        if not any(patch):
            new_fixture_fields.append(old_field)
        if "update" in patch:
            setattr(old_field, "field_name", patch["update"])
            new_fixture_fields.append(old_field)
        if "remove" in patch:
            continue
    new_fields = fields_patches.keys()
    for new_field_name in new_fields:
        patch = fields_patches.pop(new_field_name)
        if "is_new" in patch:
            new_fixture_fields.append(FixtureTypeField(
                field_name=new_field_name,
                properties=[]
            ))
    setattr(data_type, "fields", new_fixture_fields)
    transaction.save(data_type)
    return data_type


def update_items(fields_patches, domain, data_type_id, transaction):
    data_items = FixtureDataItem.by_data_type(domain, data_type_id)
    for item in data_items:
        fields = item.fields
        updated_fields = {}
        patches = deepcopy(fields_patches)
        for old_field in fields.keys():
            patch = patches.pop(old_field, {})
            if not any(patch):
                updated_fields[old_field] = fields.pop(old_field)
            if "update" in patch:
                new_field_name = patch["update"]
                updated_fields[new_field_name] = fields.pop(old_field)
            if "remove" in patch:
                continue
                # destroy_field(field_to_delete, transaction)
        for new_field_name in patches.keys():
            patch = patches.pop(new_field_name, {})
            if "is_new" in patch:
                updated_fields[new_field_name] = FieldList(
                    field_list=[]
                )
        setattr(item, "fields", updated_fields)
        transaction.save(item)
    data_items = FixtureDataItem.by_data_type(domain, data_type_id)



def create_types(fields_patches, domain, data_tag, is_global, transaction):
    data_type = FixtureDataType(
        domain=domain,
        tag=data_tag,
        is_global=is_global,
        fields=[FixtureTypeField(field_name=field, properties=[]) for field in fields_patches]
    )
    transaction.save(data_type)
    return data_type

@require_can_edit_fixtures
def data_table(request, domain):
    sheets = download_item_lists(request, domain, html_response=True)
    sheets.pop("types")
    if not sheets:
        return {
            "headers": DataTablesHeader(DataTablesColumn("No lookup Tables Uploaded")),
            "rows": []
        }
    selected_sheet = sheets.values()[0]
    data_table = {
        "headers": None,
        "rows": None
    }
    headers = [DataTablesColumn(header) for header in selected_sheet["headers"]]
    data_table["headers"] = DataTablesHeader(*headers)
    if selected_sheet["headers"] and selected_sheet["rows"]:
        data_table["rows"] = [[format_datatables_data(x or "--", "a") for x in row] for row in selected_sheet["rows"]]
    else:
        messages.info(request, _("No items are added in this table type. Upload using excel to add some rows to this table"))
        data_table["rows"] = [["--" for x in range(0, len(headers))]]
    return data_table

DELETE_HEADER = "Delete(Y/N)"

@require_can_edit_fixtures
def download_item_lists(request, domain, html_response=False):
    """
        Is used to serve excel_download and html_view for view_lookup_tables
    """
    table_ids = request.GET.getlist("table_id")
    if table_ids and table_ids[0]:
        try:
            data_types_view = [FixtureDataType.get(id) for id in request.GET.getlist("table_id")]
        except ResourceNotFound:
            messages.info(request, _("Sorry, we couldn't find that table. If you think this is a mistake please report an issue."))
            data_types_view = FixtureDataType.by_domain(domain)
    else:
        data_types_view = FixtureDataType.by_domain(domain)

    if html_response:
        data_types_view = list(data_types_view)[0:1]
    # book-keeping data from view_results for repeated use
    data_types_book = []
    data_items_boook_by_type = {}
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
          {u'clinics': {'field 2 : property 1': u'lang'}, u'growth_chart': {'field 2 : property 2': u'maxWeight'}}
    """
    type_field_properties = {}
    get_field_prop_format = lambda x, y: "field " + str(x) + " : property " + str(y)
    for data_type in data_types_view:
        # Helpers to generate 'types' sheet
        type_field_properties[data_type.tag] = {}
        data_types_book.append(data_type)
        if len(data_type.fields) > max_fields:
            max_fields = len(data_type.fields)
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
        data_items_boook_by_type[data_type.tag] = []
        max_users = 0
        max_groups = 0
        max_field_prop_combos = {field_name: 0 for field_name in data_type.fields_without_attributes}
        for item_row in FixtureDataItem.by_data_type(domain, data_type.get_id):
            data_items_boook_by_type[data_type.tag].append(item_row)
            group_len = len(item_row.get_groups())
            max_groups = group_len if group_len > max_groups else max_groups
            user_len = len(item_row.get_users())
            max_users = user_len if user_len > max_users else max_users
            for field_key in item_row.fields:
                max_combos = max_field_prop_combos[field_key]
                cur_combo_len = len(item_row.fields[field_key].field_list)
                max_combos = cur_combo_len if cur_combo_len > max_combos else max_combos
                max_field_prop_combos[field_key] = max_combos
        item_helpers = {
            "max_users": max_users,
            "max_groups": max_groups,
            "max_field_prop_combos": max_field_prop_combos,
        }
        item_helpers_by_type[data_type.tag] = item_helpers

    # Prepare 'types' sheet data
    types_sheet = {"headers": [], "rows": []}
    types_sheet["headers"] = [DELETE_HEADER, "table_id", 'is_global?']
    types_sheet["headers"].extend(["field %d" % x for x in range(1, max_fields + 1)])
    field_prop_headers = []
    for field_num, prop_num in enumerate(field_prop_count):
        if prop_num > 0:
            for c in range(0, prop_num):
                prop_key = get_field_prop_format(field_num + 1, c + 1)
                field_prop_headers.append(prop_key)
                types_sheet["headers"].append(prop_key)

    for data_type in data_types_book:
        common_vals = ["N", data_type.tag, yesno(data_type.is_global)]
        field_vals = [field.field_name for field in data_type.fields] + empty_padding_list(max_fields - len(data_type.fields))
        prop_vals = []
        if type_field_properties.has_key(data_type.tag):
            props = type_field_properties.get(data_type.tag)
            prop_vals.extend([props.get(key, "") for key in field_prop_headers])
        row = tuple(common_vals[2 if html_response else 0:] + field_vals + prop_vals)
        types_sheet["rows"].append(row)

    types_sheet["rows"] = tuple(types_sheet["rows"])
    types_sheet["headers"] = tuple(types_sheet["headers"])
    excel_sheets["types"] = types_sheet
    
    # Prepare 'items' sheet data for each data-type
    for data_type in data_types_book:
        item_sheet = {"headers": [], "rows": []}
        item_helpers = item_helpers_by_type[data_type.tag]
        max_users = item_helpers["max_users"]
        max_groups = item_helpers["max_groups"]
        max_field_prop_combos = item_helpers["max_field_prop_combos"]
        common_headers = ["UID", DELETE_HEADER]
        user_headers = ["user %d" % x for x in range(1, max_users + 1)]
        group_headers = ["group %d" % x for x in range(1, max_groups + 1)]
        field_headers = []
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
            common_headers[2 if html_response else 0:] + field_headers + user_headers + group_headers
        )
        excel_sheets[data_type.tag] = item_sheet
        for item_row in data_items_boook_by_type[data_type.tag]:
            common_vals = [str(_id_from_doc(item_row)), "N"]
            user_vals = [user.raw_username for user in item_row.get_users()] + empty_padding_list(max_users - len(item_row.get_users()))
            group_vals = [group.name for group in item_row.get_groups()] + empty_padding_list(max_groups - len(item_row.get_groups()))
            field_vals = []
            for field in data_type.fields:
                if len(field.properties) == 0:
                    if any(item_row.fields.get(field.field_name).field_list):
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
                    padding_list_len = (max_field_prop_combos[field.field_name] - cur_combo_count) * (cur_prop_count + 1)
                    field_prop_vals.extend(empty_padding_list(padding_list_len))
                    # import pdb; pdb.set_trace();
                    field_vals.extend(field_prop_vals)
            row = tuple(
                common_vals[2 if html_response else 0:] + field_vals + user_vals + group_vals
            )
            item_sheet["rows"].append(row)
        item_sheet["rows"] = tuple(item_sheet["rows"])
        excel_sheets[data_type.tag] = item_sheet

    if html_response:
        return excel_sheets

    header_groups = [("types", excel_sheets["types"]["headers"])]
    value_groups = [("types", excel_sheets["types"]["rows"])]
    for data_type in data_types_book:
        header_groups.append((data_type.tag, excel_sheets[data_type.tag]["headers"]))
        value_groups.append((data_type.tag, excel_sheets[data_type.tag]["rows"]))

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as temp:
        export_raw(tuple(header_groups), tuple(value_groups), temp)
    format = Format.XLS_2007

    fl = open(path, 'r')
    fileref = expose_download(
        fl.read(),
        60 * 10,
        mimetype=Format.from_format(format).mimetype,
        content_disposition='attachment; filename="%s_fixtures.xlsx"' % domain,
    )
    return json_response({"download_id": fileref.download_id})

@require_can_edit_fixtures
def download_file(request, domain):
    download_id = request.GET.get("download_id")
    try:
        dw = CachedDownload.get(download_id)
        if dw:
            return dw.toHttpResponse()
        else:
            raise IOError
    except IOError:
        notify_exception(request)
        messages.error(request, _("Sorry, Something went wrong with your download! Please try again. If you see this repeatedly please report an issue "))
        return HttpResponseRedirect(reverse("fixture_interface_dispatcher", args=[], kwargs={'domain': domain, 'report_slug': 'edit_lookup_tables'}))


class UploadItemLists(TemplateView):

    def get_context_data(self, **kwargs):
        """TemplateView automatically calls this to render the view (on a get)"""
        return {
            'domain': self.domain
        }

    def get(self, request):
        return HttpResponseRedirect(reverse("fixture_interface_dispatcher", args=[], kwargs={'domain': self.domain, 'report_slug': 'edit_lookup_tables'}))
    @method_decorator(get_file)
    def post(self, request):
        """View's dispatch method automatically calls this"""

        def error_redirect():
            return HttpResponseRedirect(reverse("fixture_interface_dispatcher", args=[], kwargs={'domain': self.domain, 'report_slug': 'edit_lookup_tables'}))

        try:
            replace = request.POST["replace"]
            replace = True
        except KeyError:
            replace = False

        try:
            workbook = WorkbookJSONReader(request.file)
        except AttributeError:
            messages.error(request, _("Error processing your Excel (.xlsx) file"))
            return error_redirect()
        except Exception as e:
            messages.error(request, _("Invalid file-format. Please upload a valid xlsx file."))
            return error_redirect()

        try:
            upload_result = run_upload(request, self.domain, workbook, replace=replace)
            if upload_result["unknown_groups"]:
                for group_name in upload_result["unknown_groups"]:
                    messages.error(request, _("Unknown group: '%(name)s'") % {'name': group_name})
            if upload_result["unknown_users"]:
                for user_name in upload_result["unknown_users"]:
                    messages.error(request, _("Unknown user: '%(name)s'") % {'name': user_name})
        except WorksheetNotFound as e:
            messages.error(request, _("Workbook does not contain a sheet called '%(title)s'") % {'title': e.title})
            return error_redirect()
        except ExcelMalformatException as e:
            messages.error(request, _("Uploaded excel file has following formatting-problems: '%(e)s'") % {'e': e})
            return error_redirect()
        except DuplicateFixtureTagException as e:
            messages.error(request, e)
        except FixtureAPIException as e:
            messages.error(request, _(str(e)))
            return error_redirect()
        except Exception as e:
            notify_exception(request, message=str(e))
            messages.error(request, str(e))
            messages.error(request, _("Fixture upload failed for some reason and we have noted this failure. "
                                      "Please make sure the excel file is correctly formatted and try again."))
            return error_redirect()

        return HttpResponseRedirect(reverse("fixture_interface_dispatcher", args=[], kwargs={'domain': self.domain, 'report_slug': 'edit_lookup_tables'}))

    @method_decorator(require_can_edit_fixtures)
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(UploadItemLists, self).dispatch(request, *args, **kwargs)

@require_POST
@login_or_digest
@require_can_edit_fixtures
def upload_fixture_api(request, domain, **kwargs):
    """
        Use following curl-command to test.
        > curl -v --digest http://127.0.0.1:8000/a/gsid/fixtures/fixapi/ -u user@domain.com:password
                -F "file-to-upload=@hqtest_fixtures.xlsx"
                -F "replace=true"
    """
    response_codes = {"fail": 405, "warning": 402, "success": 200}
    error_messages = {
        "invalid_post_req": "Invalid post request. Submit the form with field 'file-to-upload' and POST parameter 'replace'",
        "has_no_permission": "User {attr} doesn't have permission to upload fixtures",
        "invalid_file": "Error processing your file. Submit a valid (.xlsx) file",
        "has_no_sheet": "Workbook does not have a sheet called {attr}",
        "unknown_fail": "Fixture upload couldn't succeed due to the following error: {attr}",
    }

    def _return_response(code, message):
        resp_json = {}
        resp_json["code"] = code
        resp_json["message"] = message
        return HttpResponse(json.dumps(resp_json), mimetype="application/json")

    try:
        upload_file = request.FILES["file-to-upload"]
        replace = request.POST["replace"]
        if replace.lower() == "true":
            replace = True
        elif replace.lower() == "false":
            replace = False
    except Exception:
        return _return_response(response_codes["fail"], error_messages["invalid_post_req"])

    if not request.couch_user.has_permission(domain, Permissions.edit_data.name):
        error_message = error_messages["has_no_permission"].format(attr=request.couch_user.username)
        return _return_response(response_codes["fail"], error_message)

    try:
        workbook = WorkbookJSONReader(upload_file)
    except Exception:
        return _return_response(response_codes["fail"], error_messages["invalid_file"])

    try:
        upload_resp = run_upload(request, domain, workbook, replace=replace)  # error handle for other files
    except WorksheetNotFound as e:
        error_message = error_messages["has_no_sheet"].format(attr=e.title)
        return _return_response(response_codes["fail"], error_message)
    except ExcelMalformatException as e:
        notify_exception(request)
        return _return_response(response_codes["fail"], str(e))
    except DuplicateFixtureTagException as e:
        return _return_response(response_codes["fail"], str(e))
    except FixtureAPIException as e:
        return _return_response(response_codes["fail"], str(e))
    except Exception as e:
        notify_exception(request, message=e)
        error_message = error_messages["unknown_fail"].format(attr=e)
        return _return_response(response_codes["fail"], error_message)

    num_unknown_groups = len(upload_resp["unknown_groups"])
    num_unknown_users = len(upload_resp["unknown_users"])
    resp_json = {}

    if not num_unknown_users and not num_unknown_groups:
        num_uploads = upload_resp["number_of_fixtures"]
        success_message = "Successfully uploaded %d fixture%s." % (num_uploads, 's' if num_uploads > 1 else '')
        return _return_response(response_codes["success"], success_message)
    else:
        resp_json["code"] = response_codes["warning"]

    warn_groups = "%d group%s unknown" % (num_unknown_groups, 's are' if num_unknown_groups > 1 else ' is')
    warn_users = "%d user%s unknown" % (num_unknown_users, 's are' if num_unknown_users > 1 else ' is')
    resp_json["message"] = "Fixtures have been uploaded. But following "
    if num_unknown_groups:
        resp_json["message"] += "%s %s" % (warn_groups, upload_resp["unknown_groups"])
    if num_unknown_users:
        resp_json["message"] += "%s%s%s" % (("and following " if num_unknown_groups else ""), warn_users, upload_resp["unknown_users"])

    return HttpResponse(json.dumps(resp_json), mimetype="application/json")


def run_upload(request, domain, workbook, replace=False):
    return_val = {
        "unknown_groups": [], 
        "unknown_users": [], 
        "number_of_fixtures": 0,
    }
    failure_messages = {
        "has_no_column": "Workbook 'types' has no column '{column_name}'.",
        "has_no_field_column": "Excel-sheet '{tag}' does not contain the column '{field}' "
                               "as specified in its 'types' definition",
        "has_extra_column": "Excel-sheet '{tag}' has an extra column" + 
                            "'{field}' that's not defined in its 'types' definition",
        "wrong_property_syntax": "Properties should be specified as 'field 1: property 1'. In 'types' sheet, " +
                            "'{prop_key}' for field '{field}' is not correctly formatted",
        "sheet_has_no_property": "Excel-sheet '{tag}' does not contain property " +
                            "'{property}' of the field '{field}' as specified in its 'types' definition",
        "sheet_has_extra_property": "Excel-sheet '{tag}'' has an extra property " +
                            "'{property}' for the field '{field}' that's not defined in its 'types' definition. Re-check the formatting", 
        "invalid_field_with_property": "Fields with attributes should be numbered as 'field: {field} integer",
        "invalid_property": "Attribute should be written as '{field}: {prop} interger'",
        "wrong_field_property_combos": "Number of values for field '{field}' and attribute '{prop}' should be same",
        "replace_with_UID": "Rows shouldn't contain UIDs while using replace option. Excel sheet '{tag}' contains UID in a row."
    }

    group_memoizer = GroupMemoizer(domain)

    data_types = workbook.get_worksheet(title='types')

    def _get_or_raise(container, attr):
        try:
            return container[attr]
        except KeyError:
            raise ExcelMalformatException(_(failure_messages["has_no_column"].format(column_name=attr)))

    def diff_lists(list_a, list_b):
        set_a = set(list_a)
        set_b = set(list_b)
        not_in_b = set_a.difference(set_b)
        not_in_a = set_a.difference(set_a)
        return list(not_in_a), list(not_in_b)
   
    number_of_fixtures = -1
    with CouchTransaction() as transaction:
        fixtures_tags = []
        type_sheets = []
        for number_of_fixtures, dt in enumerate(data_types):
            try:
                tag = _get_or_raise(dt, 'table_id')
            except ExcelMalformatException:
                tag = _get_or_raise(dt, 'tag')
            if tag in fixtures_tags:
                error_message = "Upload Failed: Lookup-tables should have unique 'table_id'. There are two rows with table_id '{tag}' in 'types' sheet."
                raise DuplicateFixtureTagException(_(error_message.format(tag=tag)))
            fixtures_tags.append(tag)
            type_sheets.append(dt)
        for number_of_fixtures, dt in enumerate(type_sheets):
            try:
                tag = _get_or_raise(dt, 'table_id')
            except ExcelMalformatException:
                messages.info(request, _("Excel-header 'tag' is renamed as 'table_id' and 'name' header is no longer needed."))
                tag = _get_or_raise(dt, 'tag')

            type_definition_fields = _get_or_raise(dt, 'field')
            type_fields_with_properties = []
            for count, field in enumerate(type_definition_fields):
                prop_key = "field " + str(count + 1)
                if dt.has_key(prop_key):
                    try:
                        property_list = dt[prop_key]["property"]
                    except KeyError:
                        error_message = failure_messages["wrong_property_syntax"].format(
                            prop_key=prop_key,
                            field=field
                        )
                        raise ExcelMalformatException(_(error_message))
                else:
                    property_list = []
                field_with_prop = FixtureTypeField(
                    field_name=field,
                    properties=property_list
                )
                type_fields_with_properties.append(field_with_prop)

            new_data_type = FixtureDataType(
                domain=domain,
                is_global=dt.get('is_global', False),
                tag=tag,
                fields=type_fields_with_properties,
            )
            try:
                tagged_fdt = FixtureDataType.fixture_tag_exists(domain, tag)
                if tagged_fdt:
                    data_type = tagged_fdt
                # support old usage with 'UID'
                elif 'UID' in dt and dt['UID']:
                    data_type = FixtureDataType.get(dt['UID'])
                else:
                    data_type = new_data_type
                    pass
                if replace:
                    data_type.recursive_delete(transaction)
                    data_type = new_data_type
                data_type.fields = type_fields_with_properties
                data_type.is_global = dt.get('is_global', False)
                assert data_type.doc_type == FixtureDataType._doc_type
                if data_type.domain != domain:
                    data_type = new_data_type
                    messages.error(request, _("'%(UID)s' is not a valid UID. But the new type is created.") % {'UID': dt['UID']})
                if dt[DELETE_HEADER] == "Y" or dt[DELETE_HEADER] == "y":
                    data_type.recursive_delete(transaction)
                    continue
            except (ResourceNotFound, KeyError) as e:
                data_type = new_data_type
            transaction.save(data_type)

            data_items = workbook.get_worksheet(data_type.tag)
            for sort_key, di in enumerate(data_items):
                # Check that type definitions in 'types' sheet vs corresponding columns in the item-sheet MATCH
                item_fields_list = di['field'].keys()
                not_in_sheet, not_in_types = diff_lists(item_fields_list, data_type.fields_without_attributes)
                if len(not_in_sheet) > 0:
                    error_message = failure_messages["has_no_field_column"].format(tag=tag, field=not_in_sheet[0])
                    raise ExcelMalformatException(_(error_message))
                if len(not_in_types) > 0:
                    error_message = failure_messages["has_extra_column"].format(tag=tag, field=not_in_types[0])
                    raise ExcelMalformatException(_(error_message))

                # check that properties in 'types' sheet vs item-sheet MATCH
                for field in data_type.fields:
                    if len(field.properties) > 0:
                        sheet_props = di.get(field.field_name, {})
                        sheet_props_list = sheet_props.keys()
                        type_props = field.properties
                        not_in_sheet, not_in_types = diff_lists(sheet_props_list, type_props)
                        if len(not_in_sheet) > 0:
                            error_message = failure_messages["sheet_has_no_property"].format(
                                tag=tag,
                                property=not_in_sheet[0],
                                field=field.field_name
                            )
                            raise ExcelMalformatException(_(error_message))
                        if len(not_in_types) > 0:
                            error_message = failure_messages["sheet_has_extra_property"].format(
                                tag=tag,
                                property=not_in_types[0],
                                field=field.field_name
                            )
                            raise ExcelMalformatException(_(error_message))
                        # check that fields with properties are numbered
                        if type(di['field'][field.field_name]) != list:
                            error_message = failure_messages["invalid_field_with_property"].format(field=field.field_name)
                            raise ExcelMalformatException(_(error_message))
                        field_prop_len = len(di['field'][field.field_name])
                        for prop in sheet_props:
                            if type(sheet_props[prop]) != list:
                                error_message = failure_messages["invalid_property"].format(
                                    field=field.field_name,
                                    prop=prop
                                )
                                raise ExcelMalformatException(_(error_message))
                            if len(sheet_props[prop]) != field_prop_len:
                                error_message = failure_messages["wrong_field_property_combos"].format(
                                    field=field.field_name,
                                    prop=prop
                                )
                                raise ExcelMalformatException(_(error_message))

                # excel format check should have been covered by this line. Can make assumptions about data now
                type_fields = data_type.fields
                item_fields = {}
                for field in type_fields:
                    # if field doesn't have properties
                    if len(field.properties) == 0:
                        item_fields[field.field_name] = FieldList(
                            field_list=[FixtureItemField(
                                # using unicode here, to cast ints, and multi-language strings
                                field_value=unicode(di['field'][field.field_name]),
                                properties={}
                            )]
                        )
                    else:
                        field_list = []
                        field_prop_combos = di['field'][field.field_name]
                        prop_combo_len = len(field_prop_combos)
                        prop_dict = di[field.field_name]
                        for x in range(0, prop_combo_len):
                            fix_item_field = FixtureItemField(
                                field_value=unicode(field_prop_combos[x]),
                                properties={prop: unicode(prop_dict[prop][x]) for prop in prop_dict}
                            )
                            field_list.append(fix_item_field)
                        item_fields[field.field_name] = FieldList(
                            field_list=field_list
                        )

                new_data_item = FixtureDataItem(
                    domain=domain,
                    data_type_id=data_type.get_id,
                    fields=item_fields,
                    sort_key=sort_key
                )
                try:
                    if di['UID'] and not replace:
                        old_data_item = FixtureDataItem.get(di['UID'])
                    else:
                        old_data_item = new_data_item
                        pass
                    old_data_item.fields = item_fields   
                    if old_data_item.domain != domain or not old_data_item.data_type_id == data_type.get_id:
                        old_data_item = new_data_item
                        messages.error(request, _("'%(UID)s' is not a valid UID. But the new item is created.") % {'UID': di['UID']})
                    assert old_data_item.doc_type == FixtureDataItem._doc_type
                    if di[DELETE_HEADER] == "Y" or di[DELETE_HEADER] == "y":
                        old_data_item.recursive_delete(transaction)
                        continue               
                except (ResourceNotFound, KeyError) as e:
                    old_data_item = new_data_item
                transaction.save(old_data_item)

                old_groups = old_data_item.get_groups()
                for group in old_groups:
                    old_data_item.remove_group(group)
                old_users = old_data_item.get_users()
                for user in old_users:
                    old_data_item.remove_user(user)

                for group_name in di.get('group', []):
                        group = group_memoizer.by_name(group_name)
                        if group:
                            old_data_item.add_group(group, transaction=transaction)
                        else:
                            messages.error(request, _("Unknown group: '%(name)s'. But the row is successfully added") % {'name': group_name})

                for raw_username in di.get('user', []):
                        try:
                            username = normalize_username(raw_username, domain)
                        except ValidationError:
                            messages.error(request, _("Invalid username: '%(name)s'. Row is not added") % {'name': raw_username})
                            continue
                        user = CommCareUser.get_by_username(username)
                        if user:
                            old_data_item.add_user(user)
                        else:
                            messages.error(request, _("Unknown user: '%(name)s'. But the row is successfully added") % {'name': raw_username})

    return_val["number_of_fixtures"] = number_of_fixtures + 1
    return return_val
