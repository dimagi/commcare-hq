import json
from couchdbkit import ResourceNotFound
from collections import OrderedDict

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseBadRequest, HttpResponseRedirect, Http404, HttpResponse
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView

from corehq.apps.domain.decorators import login_or_digest, login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.fixtures.tasks import fixture_upload_async, fixture_download_async
from corehq.apps.fixtures.dispatcher import require_can_edit_fixtures
from corehq.apps.fixtures.download import prepare_fixture_download, prepare_fixture_html
from corehq.apps.fixtures.exceptions import (
    FixtureDownloadError,
    ExcelMalformatException,
    FixtureAPIException,
    DuplicateFixtureTagException,
    FixtureUploadError
)
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem, FieldList, FixtureTypeField
from corehq.apps.fixtures.upload import run_upload, validate_file_format, get_workbook
from corehq.apps.fixtures.fixturegenerators import item_lists_by_domain
from corehq.apps.fixtures.utils import is_field_name_invalid
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import Permissions
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.excel import WorksheetNotFound, JSONReaderError, \
    HeaderValueError
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.utils.decorators.view import get_file

from copy import deepcopy
from soil import CachedDownload, DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context


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
    return dict((str(k), v) for k, v in json.load(req, object_pairs_hook=OrderedDict).items())

@require_can_edit_fixtures
def tables(request, domain):
    if request.method == 'GET':
        return json_response([strip_json(x) for x in FixtureDataType.by_domain(domain)])

@require_can_edit_fixtures
def update_tables(request, domain, data_type_id, test_patch=None):
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
    if test_patch is None:
        test_patch = {}
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

        # validate fields
        validation_errors = []
        for field_name, options in fields_update['fields'].items():
            method = options.keys()
            if 'update' in method:
                field_name = options['update']
            if field_name.startswith('xml') and 'remove' not in method:
                validation_errors.append(
                    _("Field name \"%s\" cannot begin with 'xml'.") % field_name
                )
            if is_field_name_invalid(field_name) and 'remove' not in method:
                validation_errors.append(
                    _("Field name \"%s\" cannot include /, "
                      "\\, <, >, or spaces.") % field_name
                )
        if validation_errors:
            return json_response({
                'validation_errors': validation_errors,
                'error_msg': _(
                    "Could not update table because field names were not "
                    "correctly formatted"),
            })

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
    # TODO this should be async (large tables time out)
    table_ids = request.GET.getlist("table_id")
    try:
        sheets = prepare_fixture_html(table_ids, domain)
    except FixtureDownloadError as e:
        messages.info(request, unicode(e))
        raise Http404()
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
def download_item_lists(request, domain):
    """Asynchronously serve excel download for edit_lookup_tables
    """
    download = DownloadBase()
    download.set_task(fixture_download_async.delay(
        prepare_fixture_download,
        table_ids=request.POST.getlist("table_ids[]", []),
        domain=domain,
        download_id=download.download_id,
    ))
    return download.get_start_response()


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

        file_ref = expose_cached_download(request.file.read(),
                                   expiry=1*60*60)

        # catch basic validation in the synchronous UI
        try:
            validate_file_format(file_ref.get_filename())
        except (FixtureUploadError, JSONReaderError, HeaderValueError) as e:
            messages.error(request, _(u'Upload unsuccessful: %s') % e)
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
        return render(request, 'style/bootstrap2/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_fixtures
def fixture_upload_job_poll(request, domain, download_id, template="fixtures/partials/fixture_upload_status.html"):
    try:
        context = get_download_context(download_id, check_state=True)
    except TaskFailedError:
        return HttpResponseServerError()

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
        return HttpResponse(json.dumps(resp_json), content_type="application/json")

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

    return HttpResponse(json.dumps(resp_json), content_type="application/json")


@login_and_domain_required
def fixture_metadata(request, domain):
    """
    Returns list of fixtures and metadata needed for itemsets in vellum
    """
    return json_response(item_lists_by_domain(domain))
