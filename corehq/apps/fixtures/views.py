import json
import os
import tempfile
from couchdbkit import ResourceNotFound

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseBadRequest, HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import render
from django.template.defaultfilters import yesno
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView

from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.fixtures.tasks import fixture_upload_async
from corehq.apps.fixtures.dispatcher import require_can_edit_fixtures
from corehq.apps.fixtures.exceptions import ExcelMalformatException, FixtureAPIException, DuplicateFixtureTagException, \
    FixtureUploadError
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, _id_from_doc, FieldList, FixtureTypeField
from corehq.apps.fixtures.upload import run_upload, DELETE_HEADER, validate_file_format, get_workbook
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import Permissions
from couchexport.export import export_raw
from couchexport.models import Format
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.excel import WorksheetNotFound
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.utils.decorators.view import get_file

from copy import deepcopy
from soil import CachedDownload
from soil.util import expose_download, get_download_context


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
        fields=[FixtureTypeField(field_name=field, properties=[]) for field in fields_patches],
        item_attributes=[],
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
    selected_sheet_tag = sheets.keys()[0]
    data_table = {
        "headers": None,
        "rows": None,
        "table_id": selected_sheet_tag
    }
    headers = [DataTablesColumn(header) for header in selected_sheet["headers"]]
    data_table["headers"] = DataTablesHeader(*headers)
    if selected_sheet["headers"] and selected_sheet["rows"]:
        data_table["rows"] = [[format_datatables_data(x or "--", "a") for x in row] for row in selected_sheet["rows"]]
    else:
        messages.info(request, _("No items are added in this table type. Upload using excel to add some rows to this table"))
        data_table["rows"] = [["--" for x in range(0, len(headers))]]
    return data_table


@require_can_edit_fixtures
def download_item_lists(request, domain, html_response=False):
    """
        Is used to serve excel_download and html_view for view_lookup_tables
    """
    table_ids = request.GET.getlist("table_id")
    if table_ids and table_ids[0]:
        try:
            data_types_view = [FixtureDataType.get(id) for id in request.GET.getlist("table_id")]
        except ResourceNotFound as Ex:
            if html_response:
                messages.info(request, _("Sorry, we couldn't find that table. If you think this is a mistake please report an issue."))
                raise
            data_types_view = FixtureDataType.by_domain(domain)
    else:
        data_types_view = FixtureDataType.by_domain(domain)

    if html_response:
        data_types_view = list(data_types_view)[0:1]
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
        max_field_prop_combos = {field_name: 0 for field_name in data_type.fields_without_attributes}
        for item_row in FixtureDataItem.by_data_type(domain, data_type.get_id):
            data_items_book_by_type[data_type.tag].append(item_row)
            group_len = len(item_row.groups)
            max_groups = group_len if group_len > max_groups else max_groups
            user_len = len(item_row.users)
            max_users = user_len if user_len > max_users else max_users
            for field_key in item_row.fields:
                if field_key in max_field_prop_combos:
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
        field_vals = [field.field_name for field in data_type.fields] + empty_padding_list(max_fields - len(data_type.fields))
        item_att_vals = data_type.item_attributes + empty_padding_list(max_item_attributes - len(data_type.item_attributes))
        prop_vals = []
        if type_field_properties.has_key(data_type.tag):
            props = type_field_properties.get(data_type.tag)
            prop_vals.extend([props.get(key, "") for key in field_prop_headers])
        row = tuple(common_vals[2 if html_response else 0:] + field_vals + item_att_vals + prop_vals)
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
            common_headers[2 if html_response else 0:] + field_headers + item_att_headers + user_headers + group_headers
        )
        excel_sheets[data_type.tag] = item_sheet
        for item_row in data_items_book_by_type[data_type.tag]:
            common_vals = [str(_id_from_doc(item_row)), "N"]
            user_vals = [user.raw_username for user in item_row.users] + empty_padding_list(max_users - len(item_row.users))
            group_vals = [group.name for group in item_row.groups] + empty_padding_list(max_groups - len(item_row.groups))
            field_vals = []
            item_att_vals = [item_row.item_attributes[attribute] for attribute in data_type.item_attributes]
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
                common_vals[2 if html_response else 0:] + field_vals + item_att_vals + user_vals + group_vals
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


def fixtures_home(domain):
    return reverse("fixture_interface_dispatcher", args=[],
                   kwargs={'domain': domain, 'report_slug': 'edit_lookup_tables'})


class FixtureViewMixIn(object):
    section_name = ugettext_noop("Lookup Tables")

    @property
    def section_url(self):
        return fixtures_home(self.domain)


class UploadItemLists(TemplateView):

    def get_context_data(self, **kwargs):
        """TemplateView automatically calls this to render the view (on a get)"""
        return {
            'domain': self.domain
        }

    def get(self, request):
        return HttpResponseRedirect(fixtures_home(self.domain))

    @method_decorator(get_file)
    def post(self, request):
        replace = 'replace' in request.POST

        file_ref = expose_download(request.file.read(),
                                   expiry=1*60*60)

        # catch basic validation in the synchronous UI
        try:
            validate_file_format(file_ref.get_filename())
        except FixtureUploadError as e:
            messages.error(request, unicode(e))
            return HttpResponseRedirect(fixtures_home(self.domain))

        # hand off to async
        task = fixture_upload_async.delay(
            self.domain,
            file_ref.download_id,
            replace,
        )
        file_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                FixtureUploadStatusView.urlname,
                args=[self.domain, file_ref.download_id]
            )
        )

    @method_decorator(require_can_edit_fixtures)
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(UploadItemLists, self).dispatch(request, *args, **kwargs)


class FixtureUploadStatusView(FixtureViewMixIn, BaseDomainView):
    urlname = 'fixture_upload_status'
    page_title = ugettext_noop('Lookup Table Upload Status')

    def get(self, request, *args, **kwargs):
        context = super(FixtureUploadStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('fixture_upload_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _(self.page_title),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
        })
        return render(request, 'hqwebapp/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_fixtures
def fixture_upload_job_poll(request, domain, download_id, template="fixtures/partials/fixture_upload_status.html"):
    context = get_download_context(download_id, check_state=True)
    context.update({
        'on_complete_short': _('Upload complete.'),
        'on_complete_long': _('Lookup table upload has finished'),

    })
    return render(request, template, context)


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
        workbook = get_workbook(upload_file)
    except Exception:
        return _return_response(response_codes["fail"], error_messages["invalid_file"])

    try:
        upload_resp = run_upload(domain, workbook, replace=replace)  # error handle for other files
    except WorksheetNotFound as e:
        error_message = error_messages["has_no_sheet"].format(attr=e.title)
        return _return_response(response_codes["fail"], error_message)
    except ExcelMalformatException as e:
        return _return_response(response_codes["fail"], str(e))
    except DuplicateFixtureTagException as e:
        return _return_response(response_codes["fail"], str(e))
    except FixtureAPIException as e:
        return _return_response(response_codes["fail"], str(e))
    except Exception as e:
        error_message = error_messages["unknown_fail"].format(attr=e)
        return _return_response(response_codes["fail"], error_message)

    num_unknown_groups = len(upload_resp.unknown_groups)
    num_unknown_users = len(upload_resp.unknown_users)
    resp_json = {}

    if not num_unknown_users and not num_unknown_groups:
        num_uploads = upload_resp.number_of_fixtures
        success_message = "Successfully uploaded %d fixture%s." % (num_uploads, 's' if num_uploads > 1 else '')
        return _return_response(response_codes["success"], success_message)
    else:
        resp_json["code"] = response_codes["warning"]

    warn_groups = "%d group%s unknown" % (num_unknown_groups, 's are' if num_unknown_groups > 1 else ' is')
    warn_users = "%d user%s unknown" % (num_unknown_users, 's are' if num_unknown_users > 1 else ' is')
    resp_json["message"] = "Fixtures have been uploaded. But following "
    if num_unknown_groups:
        resp_json["message"] += "%s %s" % (warn_groups, upload_resp.unknown_groups)
    if num_unknown_users:
        resp_json["message"] += "%s%s%s" % (("and following " if num_unknown_groups else ""), warn_users, upload_resp.unknown_users)

    return HttpResponse(json.dumps(resp_json), mimetype="application/json")
