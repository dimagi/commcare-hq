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

from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc, FieldList, FixtureTypeField, FixtureItemField
from corehq.apps.fixtures.exceptions import ExcelMalformatException
from corehq.apps.groups.models import Group
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


require_can_edit_fixtures = require_permission(Permissions.edit_data)

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
def data_types(request, domain, data_type_id):
    
    if data_type_id:
        try:
            data_type = FixtureDataType.get(data_type_id)
        except ResourceNotFound:
            raise Http404()

        assert(data_type.doc_type == FixtureDataType._doc_type)
        assert(data_type.domain == domain)

        if request.method == 'GET':
            return json_response(strip_json(data_type))

        elif request.method == 'PUT':
            new = FixtureDataType(domain=domain, **_to_kwargs(request))
            for attr in 'tag', 'name', 'fields':
                setattr(data_type, attr, getattr(new, attr))
            data_type.save()
            return json_response(strip_json(data_type))

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)
            return json_response({})

    elif data_type_id is None:

        if request.method == 'POST':
            data_type = FixtureDataType(domain=domain, **_to_kwargs(request))
            data_type.save()
            return json_response(strip_json(data_type))

        elif request.method == 'GET':
            return json_response([strip_json(x) for x in FixtureDataType.by_domain(domain)])

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                for data_type in FixtureDataType.by_domain(domain):
                    data_type.recursive_delete(transaction)
            return json_response({})

    return HttpResponseBadRequest()


def prepare_user(user):
    user.username = user.raw_username
    return strip_json(user, disallow=['password'])

@require_can_edit_fixtures
def data_items(request, domain, data_type_id, data_item_id):

    def prepare_item(item):
        ret = strip_json(item, disallow=['data_type_id'])
        if request.GET.get('groups') == 'true':
            ret['groups'] = []
            for group in item.get_groups():
                ret['groups'].append(strip_json(group))
        if request.GET.get('users') == 'true':
            ret['users'] = []
            for user in item.get_users():
                ret['users'].append(prepare_user(user))
        return ret

    if request.method == 'POST' and data_item_id is None:
        o = FixtureDataItem(domain=domain, data_type_id=data_type_id, **_to_kwargs(request))
        o.save()
        return json_response(strip_json(o, disallow=['data_type_id']))
    elif request.method == 'GET' and data_item_id is None:
        return json_response([
            prepare_item(x)
            for x in sorted(FixtureDataItem.by_data_type(domain, data_type_id),
                            key=lambda x: x.sort_key)
        ])
    elif request.method == 'GET' and data_item_id:
        try:
            o = FixtureDataItem.get(data_item_id)
        except ResourceNotFound:
            raise Http404()
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        return json_response(prepare_item(o))
    elif request.method == 'PUT' and data_item_id:
        original = FixtureDataItem.get(data_item_id)
        new = FixtureDataItem(domain=domain, **_to_kwargs(request))
        for attr in 'fields',:
            setattr(original, attr, getattr(new, attr))
        original.save()
        return json_response(strip_json(original, disallow=['data_type_id']))
    elif request.method == 'DELETE' and data_item_id:
        o = FixtureDataItem.get(data_item_id)
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        with CouchTransaction() as transaction:
            o.recursive_delete(transaction)
        return json_response({})
    else:
        return HttpResponseBadRequest()

def data_item_groups(request, domain, data_type_id, data_item_id, group_id):
    data_type = FixtureDataType.get(data_type_id)
    data_item = FixtureDataItem.get(data_item_id)
    group = Group.get(group_id)
    assert(data_type.doc_type == FixtureDataType._doc_type)
    assert(data_type.domain == domain)
    assert(data_item.doc_type == FixtureDataItem._doc_type)
    assert(data_item.domain == domain)
    assert(data_item.data_type_id == data_type_id)
    assert(group.doc_type == Group._doc_type)
    assert(group.domain == domain)

    if request.method == 'POST':
        data_item.add_group(group)
        return json_response({})
    elif request.method == 'DELETE':
        data_item.remove_group(group)
        return json_response({})
    else:
        return HttpResponseBadRequest()

def data_item_users(request, domain, data_type_id, data_item_id, user_id):
    data_type = FixtureDataType.get(data_type_id)
    data_item = FixtureDataItem.get(data_item_id)
    user = CommCareUser.get(user_id)
    assert(data_type.doc_type == FixtureDataType._doc_type)
    assert(data_type.domain == domain)
    assert(data_item.doc_type == FixtureDataItem._doc_type)
    assert(data_item.domain == domain)
    assert(data_item.data_type_id == data_type_id)
    assert(user.doc_type == CommCareUser._doc_type)
    assert(user.domain == domain)

    if request.method == 'POST':
        data_item.add_user(user)
        return json_response({})
    elif request.method == 'DELETE':
        data_item.remove_user(user)
        return json_response({})
    else:
        return HttpResponseBadRequest()

@require_can_edit_fixtures
def groups(request, domain):
    groups = Group.by_domain(domain)
    return json_response(map(strip_json, groups))

@require_can_edit_fixtures
def users(request, domain):
    users = CommCareUser.by_domain(domain)
    return json_response(map(prepare_user, users))

@require_can_edit_fixtures
def view(request, domain, template='fixtures/view.html'):
    return render(request, template, {
        'domain': domain
    })

DELETE_HEADER = "Delete(Y/N)"
@require_can_edit_fixtures
def download_item_lists(request, domain):
    data_types_view = FixtureDataType.by_domain(domain)
    # book-keeping data from views for latter use
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
    
    def _get_empty_list(length):
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
    get_field_prop_format = lambda x, y: "field " + str(x) +" : property" + str(y) 
    for data_type in data_types_view:
        # Helpers to generate 'types' sheet
        type_field_properties[data_type.name] = {}
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
                    type_field_properties[data_type.name][prop_key] = property
        # Helpers to generate item-sheets
        data_items_boook_by_type[data_type.name] = []
        max_users = 0
        max_groups = 0
        max_field_prop_combos = {field_name: 0 for field_name in data_type.fields_without_attributes}
        property_check = {field.field_name: False if len(field.properties)==0 else True for field in data_type.fields}
        for item_row in FixtureDataItem.by_data_type(domain, data_type.get_id):
            data_items_boook_by_type[data_type.name].append(item_row)
            group_len = len(item_row.get_groups())
            max_groups = group_len if group_len>max_groups else max_groups
            user_len = len(item_row.get_users())
            max_users = user_len if user_len>max_users else max_users
            for field_key in item_row.fields:
                max_combos = max_field_prop_combos[field_key]
                cur_combo_len = len(item_row.fields[field_key].field_list)
                max_combos = cur_combo_len if cur_combo_len > max_combos else max_combos
                max_field_prop_combos[field_key] = max_combos
        item_helpers = {
            "max_users": max_users, 
            "max_groups": max_groups, 
            "max_field_prop_combos": max_field_prop_combos,
            "property_check": property_check
        }
        item_helpers_by_type[data_type.name] = item_helpers

    ###########################################################################
    #                       Prepare 'types' sheet data
    ###########################################################################
    types_sheet = {"headers": [], "rows": []}
    types_sheet["headers"] = ["UID", DELETE_HEADER, "name", "tag", 'is_global?']
    types_sheet["headers"].extend(["field %d" % x for x in range(1, max_fields + 1)])
    field_prop_headers = []   
    for field_num, prop_num in enumerate(field_prop_count):
        if prop_num > 0:
            for c in range(0, prop_num):
                prop_key = get_field_prop_format(field_num + 1, c + 1)
                field_prop_headers.append(prop_key)
                types_sheet["headers"].append(prop_key)

    for data_type in data_types_book:
        common_vals = [str(_id_from_doc(data_type)), "N", data_type.name, data_type.tag, yesno(data_type.is_global)]
        field_vals = [field.field_name for field in data_type.fields] + 
                    _get_empty_list(max_fields - len(data_type.fields))
        prop_vals = []
        if type_field_properties.has_key(data_type.name):
            props = type_field_properties.get(data_type.name)
            prop_vals.extend([props.get(key, "") for key in field_prop_headers])
        row = tuple(common_vals + field_vals + prop_vals)
        types_sheet["rows"].append(row)

    excel_sheets["types"] = types_sheet
    print field_prop_count, type_field_properties, types_sheet

    ###########################################################################
    #                Prepare 'items' sheet data for each data-type
    ###########################################################################

    for data_type in data_types_book:
        item_sheet = {"headers": [], "rows": []}
        common_headers = ["UID", DELETE_HEADER]
        user_headers = []
        group_headers = []
        field_headers = []
        item_helpers = item_helpers_by_type[data_type.name]
        max_users = item_helpers["max_users"]
        max_groups = item_helpers["max_groups"]
        max_field_prop_combos = item_helpers["max_field_prop_combos"]
        for item in data_items_boook_by_type[data_type.name]:
            user_headers = ["user %d" % x for x in range(1, mmax_users + 1)]
            group_headers = ["group %d" % x for x in range(1, mmax_groups + 1)]
            for field_key in item.fields:



class UploadItemLists(TemplateView):

    template_name = 'fixtures/upload_item_lists.html'

    def get_context_data(self, **kwargs):
        """TemplateView automatically calls this to render the view (on a get)"""
        return {
            'domain': self.domain
        }

    @method_decorator(get_file)
    def post(self, request):
        """View's dispatch method automatically calls this"""

        def error_redirect():
            return HttpResponseRedirect(reverse('upload_fixtures', args=[self.domain]))

        try:
            workbook = WorkbookJSONReader(request.file)
        except AttributeError:
            messages.error(request, _("Error processing your Excel (.xlsx) file"))
            return error_redirect()
        except Exception as e:
            messages.error(request, _("Invalid file-format. Please upload a valid xlsx file."))
            return error_redirect()

        try:
            upload_result = run_upload(request, self.domain, workbook)
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
        except Exception as e:
            notify_exception(request)
            messages.error(request, _("Fixture upload failed for some reason and we have noted this failure. "
                                      "Please make sure the excel file is correctly formatted and try again."))
            return error_redirect()

        return HttpResponseRedirect(reverse('fixture_view', args=[self.domain]))

    @method_decorator(require_can_edit_fixtures)
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(UploadItemLists, self).dispatch(request, *args, **kwargs)

@require_POST
@login_or_digest
def upload_fixture_api(request, domain, **kwargs):
    response_codes = {"fail": 405, "warning": 402, "success": 200}
    error_messages = {
        "invalid_post_req": "Invalid post request. Submit the form with field 'file-to-upload' to upload a fixture",
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
        upload_resp = run_upload(request, domain, workbook) # error handle for other files
    except WorksheetNotFound as e:
        error_message = error_messages["has_no_sheet"].format(attr=e.title)
        return _return_response(response_codes["fail"], error_message)
    except ExcelMalformatException as e:
        notify_exception(request)
        return _return_response(response_codes["fail"], str(e))
    except Exception as e:
        notify_exception(request)
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
        resp_json["message"] += "%s%s%s" % (("and following " if num_unknown_groups else "" ), warn_users, upload_resp["unknown_users"])

    return HttpResponse(json.dumps(resp_json), mimetype="application/json")


def run_upload(request, domain, workbook):
    return_val = {
        "unknown_groups": [], 
        "unknown_users": [], 
        "number_of_fixtures": 0,
    }
    failure_messages = {
        "has_no_column": "Workbook 'types' has no column {column_name}.",
        "has_no_field_column": "Excel-sheet {tag} does not contain the column '{field}' "
                               "as specified in its 'types' definition",
        "has_extra_column": "Excel-sheet {tag} has an extra column" + 
                            "'{field}' that's not defined in its 'types' definition",
        "sheet_has_no_property": "Excel-sheet {tag} does not contain property " +
                            "{property} of the field {field} as specified in its 'types' definition",
        "sheet_has_extra_property": "Excel-sheet {tag} has an extra property" +
                            "{property} of the field {field} that's not defined in its 'types' definition",
        "invalid_field_with_property": "Fields with attributes should be numbered as 'field: {field} integer",
        "invalid_property": "Attribute should be written as '{field}: {prop} interger'",
        "wrong_field_property_combos": "Number of values for field {field} and attribute {prop} should be same"
    }

    group_memoizer = GroupMemoizer(domain)

    data_types = workbook.get_worksheet(title='types')

    def _get_or_raise(container, attr):
        try:
            return container[attr]
        except KeyError:
            raise ExcelMalformatException(_(failure_messages["has_no_column"].format(attr=attr)))

    def diff_lists(list_a, list_b):
        set_a = set(list_a)
        set_b = set(list_b)
        not_in_b = set_a.difference(set_b)
        not_in_a = set_a.difference(set_a)
        return list(not_in_a), list(not_in_b)
   
    number_of_fixtures = -1
    with CouchTransaction() as transaction:
        for number_of_fixtures, dt in enumerate(data_types):
            tag = _get_or_raise(dt, 'tag')
            type_definition_fields = _get_or_raise(dt, 'field')
            type_fields_with_properties = []
            for count, field in enumerate(type_definition_fields):
                prop_key = "field " + str(count + 1)
                if dt.has_key(prop_key):
                    property_list = dt[prop_key]["property"]
                else:
                    property_list = []
                field_with_prop = FixtureTypeField(
                    field_name =field,
                    properties =property_list
                    )
                type_fields_with_properties.append(field_with_prop)

            new_data_type = FixtureDataType(
                domain=domain,
                is_global=dt.get('is_global', False),
                name=_get_or_raise(dt, 'name'),
                tag=_get_or_raise(dt, 'tag'),
                fields=type_fields_with_properties,
            )
            try:
                if dt['UID']:
                    data_type = FixtureDataType.get(dt['UID'])
                else:
                    data_type = new_data_type
                    pass
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
                if len(not_in_sheet)>0:
                    error_message = failure_messages["has_no_field_column"].format(tag=tag, field=not_in_sheet[0])
                    raise ExcelMalformatException(_(error_message))
                if len(not_in_types)>0:
                    error_message = failure_messages["has_extra_column"].format(tag=tag, field=not_in_types[0])
                    raise ExcelMalformatException(_(error_message))

                # check that properties in 'types' sheet vs item-sheet MATCH
                for field in data_type.fields:
                    if len(field.properties)>0:
                        sheet_props = di.get(field.field_name, {})
                        sheet_props_list = sheet_props.keys()
                        type_props = field.properties
                        not_in_sheet, not_in_types = diff_lists(sheet_props_list, type_props)
                        if len(not_in_sheet)>0:
                            error_message = failure_messages["sheet_has_no_property"].format(
                                tag=tag,
                                property=not_in_sheet[0],
                                field=field.field_name
                            )
                            raise ExcelMalformatException(_(error_message))
                        if len(not_in_types)>0:
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
                                field_value=str(di['field'][field.field_name]),
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
                                field_value=str(field_prop_combos[x]),
                                properties={prop: str(prop_dict[prop][x]) for prop in prop_dict}
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
                    if di['UID']:
                        old_data_item = FixtureDataItem.get(di['UID'])
                    else:
                        old_data_item = new_data_item
                        pass
                    old_data_item.fields = item_fields   
                    if old_data_item.domain != domain:
                        old_data_item = new_data_item
                        messages.error(request, _("'%(UID)s' is not a valid UID. But the new item is created.") % {'UID': di['UID'] })
                    assert old_data_item.doc_type == FixtureDataItem._doc_type
                    assert old_data_item.data_type_id == data_type.get_id
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