from __future__ import absolute_import, unicode_literals

import json
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from io import open
from tempfile import NamedTemporaryFile

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic.base import TemplateView

import six
from couchdbkit import ResourceNotFound
from six.moves import range

from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_url_base, json_response
from soil import CachedDownload, DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq.apps.domain.decorators import api_auth, login_and_domain_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.fixtures.dispatcher import require_can_edit_fixtures
from corehq.apps.fixtures.download import prepare_fixture_html
from corehq.apps.fixtures.exceptions import (
    FixtureAPIRequestError,
    FixtureDownloadError,
    FixtureUploadError,
)
from corehq.apps.fixtures.fixturegenerators import item_lists_by_domain
from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    FixtureTypeField,
)
from corehq.apps.fixtures.tasks import (
    async_fixture_download,
    fixture_upload_async,
)
from corehq.apps.fixtures.upload import (
    upload_fixture_file,
    validate_fixture_file_format,
)
from corehq.apps.fixtures.utils import (
    clear_fixture_cache,
    is_identifier_invalid,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import Permissions
from corehq.toggles import SKIP_ORM_FIXTURE_UPLOAD
from corehq.util.files import file_extention_from_filename


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
def update_tables(request, domain, data_type_id):
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

        if data_type.domain != domain:
            raise Http404()

        if request.method == 'GET':
            return json_response(strip_json(data_type))

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)
            clear_fixture_cache(domain)
            return json_response({})
        elif not request.method == 'PUT':
            return HttpResponseBadRequest()

    if request.method == 'POST' or request.method == "PUT":
        fields_update = _to_kwargs(request)
        fields_patches = fields_update["fields"]
        data_tag = fields_update["tag"]
        is_global = fields_update["is_global"]
        description = fields_update["description"]

        # validate tag and fields
        validation_errors = []
        if is_identifier_invalid("{}_list".format(data_tag)):
            validation_errors.append(data_tag)
        for field_name, options in fields_update['fields'].items():
            method = list(options.keys())
            if 'update' in method:
                field_name = options['update']
            if is_identifier_invalid(field_name) and 'remove' not in method:
                validation_errors.append(field_name)
        validation_errors = [_(
            "\"%s\" cannot include special characters, begin or end with a space, "
            "or begin with \"xml\" or a number") % e for e in validation_errors
        ]
        if len(data_tag) < 1 or len(data_tag) > 31:
            validation_errors.append(_("Table ID must be between 1 and 31 characters."))

        if validation_errors:
            return json_response({
                'validation_errors': validation_errors,
                'error_msg': _(
                    "Could not update table because field names were not "
                    "correctly formatted"),
            })

        with CouchTransaction() as transaction:
            if data_type_id:
                data_type = _update_types(
                    fields_patches, domain, data_type_id, data_tag, is_global, description, transaction)
                _update_items(fields_patches, domain, data_type_id, transaction)
            else:
                if FixtureDataType.fixture_tag_exists(domain, data_tag):
                    return HttpResponseBadRequest("DuplicateFixture")
                else:
                    data_type = _create_types(
                        fields_patches, domain, data_tag, is_global, description, transaction)
        clear_fixture_cache(domain)
        return json_response(strip_json(data_type))


def _update_types(patches, domain, data_type_id, data_tag, is_global, description, transaction):
    data_type = FixtureDataType.get(data_type_id)
    fields_patches = deepcopy(patches)
    old_fields = data_type.fields
    new_fixture_fields = []
    data_type.tag = data_tag
    data_type.is_global = is_global
    data_type.description = description
    for old_field in old_fields:
        patch = fields_patches.pop(old_field.field_name, {})
        if not any(patch):
            new_fixture_fields.append(old_field)
        if "update" in patch:
            setattr(old_field, "field_name", patch["update"])
            new_fixture_fields.append(old_field)
        if "remove" in patch:
            continue
    new_fields = list(fields_patches.keys())
    for new_field_name in new_fields:
        patch = fields_patches.pop(new_field_name)
        if "is_new" in patch:
            new_fixture_fields.append(FixtureTypeField(
                field_name=new_field_name,
                properties=[]
            ))
    data_type.fields = new_fixture_fields
    transaction.save(data_type)
    return data_type


def _update_items(fields_patches, domain, data_type_id, transaction):
    data_items = FixtureDataItem.by_data_type(domain, data_type_id)
    for item in data_items:
        fields = item.fields
        updated_fields = {}
        patches = deepcopy(fields_patches)
        for old_field in list(fields):
            patch = patches.pop(old_field, {})
            if not any(patch):
                updated_fields[old_field] = fields.pop(old_field)
            if "update" in patch:
                new_field_name = patch["update"]
                updated_fields[new_field_name] = fields.pop(old_field)
            if "remove" in patch:
                continue
                # destroy_field(field_to_delete, transaction)
        for new_field_name in list(patches):
            patch = patches.pop(new_field_name, {})
            if "is_new" in patch:
                updated_fields[new_field_name] = FieldList(
                    field_list=[]
                )
        setattr(item, "fields", updated_fields)
        transaction.save(item)
    transaction.add_post_commit_action(
        lambda: FixtureDataItem.by_data_type(domain, data_type_id, bypass_cache=True)
    )


def _create_types(fields_patches, domain, data_tag, is_global, description, transaction):
    data_type = FixtureDataType(
        domain=domain,
        tag=data_tag,
        is_global=is_global,
        fields=[FixtureTypeField(field_name=field, properties=[]) for field in fields_patches],
        item_attributes=[],
        description=description,
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
        messages.info(request, six.text_type(e))
        raise Http404()
    sheets.pop("types")
    if not sheets:
        return {
            "headers": DataTablesHeader(DataTablesColumn("No lookup Tables Uploaded")),
            "rows": []
        }
    selected_sheet = list(sheets.values())[0]
    selected_sheet_tag = list(sheets.keys())[0]
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
    download.set_task(async_fixture_download.delay(
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

        file_ref = expose_cached_download(
            request.file.read(),
            file_extension=file_extention_from_filename(request.file.name),
            expiry=1*60*60,
        )

        # catch basic validation in the synchronous UI
        try:
            validate_fixture_file_format(file_ref.get_filename())
        except FixtureUploadError as e:
            messages.error(
                request, _('Please fix the following formatting issues in your Excel file: %s') %
                '<ul><li>{}</li></ul>'.format('</li><li>'.join(e.errors)),
                extra_tags='html'
            )
            return HttpResponseRedirect(fixtures_home(self.domain))

        # hand off to async
        task = fixture_upload_async.delay(
            self.domain,
            file_ref.download_id,
            replace,
            SKIP_ORM_FIXTURE_UPLOAD.enabled(self.domain),
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
            'error_text': _("Fixture upload failed for some reason and we have noted this failure. "
                            "Please make sure the Excel file is correctly formatted and try again."),
            'next_url': reverse('edit_lookup_tables', args=[self.domain]),
            'next_url_text': _("Return to manage lookup tables"),
        })
        return render(request, 'hqwebapp/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_fixtures
def fixture_upload_job_poll(request, domain, download_id, template="fixtures/partials/fixture_upload_status.html"):
    try:
        context = get_download_context(download_id, require_result=True)
    except TaskFailedError as e:
        notify_exception(request, message=six.text_type(e))
        return HttpResponseServerError()

    return render(request, template, context)


class UploadFixtureAPIResponse(object):

    response_codes = {"fail": 405, "warning": 402, "success": 200}

    def __init__(self, status, message):
        assert status in self.response_codes, \
            'status must be in {!r}: {}'.format(list(self.response_codes), status)
        self.status = status
        self.message = message

    @property
    def code(self):
        return self.response_codes[self.status]

    def get_response(self):
        return {
            'message': self.message,
            'code': self.code,
        }


class AsyncUploadFixtureAPIResponse(UploadFixtureAPIResponse):
    def __init__(self, status, message, download_id, status_url):
        super(AsyncUploadFixtureAPIResponse, self).__init__(status, message)
        self.download_id = download_id
        self.status_url = status_url

    def get_response(self):
        return {
            'message': self.message,
            'code': self.code,
            'status_url': self.status_url,
            'download_id': self.download_id,
        }


@csrf_exempt
@require_POST
@api_auth
@require_can_edit_fixtures
def upload_fixture_api(request, domain, **kwargs):
    """
        Use following curl-command to test.
        > curl -v --digest http://127.0.0.1:8000/a/gsid/fixtures/fixapi/ -u user@domain.com:password
                -F "file-to-upload=@hqtest_fixtures.xlsx"
                -F "replace=true"
    """

    upload_fixture_api_response = _upload_fixture_api(request, domain)
    return JsonResponse(upload_fixture_api_response.get_response())


@csrf_exempt
@api_auth
@require_can_edit_fixtures
def fixture_api_upload_status(request, domain, download_id, **kwargs):
    """
        Use following curl-command to test.
        > curl -v --digest http://127.0.0.1:8000/a/gsid/fixtures/fixapi/status/<download_id>/
               -u user@domain.com:password
    """
    try:
        context = get_download_context(download_id, require_result=True)
    except TaskFailedError as e:
        notify_exception(request, message=six.text_type(e))
        response = {
            'message': _("Upload did not complete. Reason: '{}'".format(six.text_type(e))),
            'error': True,
        }
        return json_response(response)

    if context.get('is_ready', False):
        response = {
            'complete': True,
            'message': _("Upload complete."),
        }
    elif context.get('error'):
        response = {
            'error': True,
            'message': context.get('error') or _("An unknown error occurred."),
        }
    else:
        progress = context.get('progress', {}).get('percent')
        response = {
            'message': _("Task in progress. {}% complete").format(progress),
            'progress': progress,
        }
    return json_response(response)


def _upload_fixture_api(request, domain):
    try:
        excel_file, replace, is_async, skip_orm = _get_fixture_upload_args_from_request(request, domain)
    except FixtureAPIRequestError as e:
        return UploadFixtureAPIResponse('fail', six.text_type(e))

    with excel_file as filename:

        if is_async:
            with open(filename, 'rb') as f:
                file_ref = expose_cached_download(
                    f.read(),
                    file_extension=file_extention_from_filename(filename),
                    expiry=1 * 60 * 60,
                )
                download_id = file_ref.download_id
                task = fixture_upload_async.delay(
                    domain,
                    download_id,
                    replace,
                    skip_orm
                )
                file_ref.set_task(task)

                status_url = "{}{}".format(
                    get_url_base(),
                    reverse('fixture_api_status', args=(domain, download_id))
                )

                return AsyncUploadFixtureAPIResponse(
                    'success', _("File has been uploaded successfully and is queued for processing."),
                    download_id, status_url
                )

        try:
            validate_fixture_file_format(filename)
        except FixtureUploadError as e:
            return UploadFixtureAPIResponse(
                'fail',
                _('Please fix the following formatting issues in your Excel file: %s')
                % '\n'.join(e.errors))

        result = upload_fixture_file(domain, filename, replace=replace)
        status = 'warning' if result.errors else 'success'
        return UploadFixtureAPIResponse(status, result.get_display_message())


@contextmanager
def _excel_upload_file(upload_file):
    """
    convert django FILES object to the filename of a tempfile
    that gets deleted when you leave the with...as block

    usage:
        with _excel_upload_file(upload_file) as filename:
            # you can now access the file by filename
            upload_fixture_file(domain, filename, replace)
            ...

    """
    with NamedTemporaryFile(suffix='.xlsx') as tempfile:
        # copy upload_file into tempfile (flush guarantees the operation is completed)
        for chunk in upload_file.chunks():
            tempfile.write(chunk)
        tempfile.flush()
        yield tempfile.name


def _get_fixture_upload_args_from_request(request, domain):
    try:
        upload_file = request.FILES["file-to-upload"]
        replace = request.POST["replace"]
        if replace.lower() == "true":
            replace = True
        elif replace.lower() == "false":
            replace = False
    except Exception:
        raise FixtureAPIRequestError(
            "Invalid post request."
            "Submit the form with field 'file-to-upload' and POST parameter 'replace'")

    is_async = request.POST.get("async", "").lower() == "true"

    if not request.couch_user.has_permission(domain, Permissions.edit_data.name):
        raise FixtureAPIRequestError(
            "User {} doesn't have permission to upload fixtures"
            .format(request.couch_user.username))

    skip_orm = False
    if request.POST.get('skip_orm') == 'true' and SKIP_ORM_FIXTURE_UPLOAD.enabled(domain):
        skip_orm = True

    return _excel_upload_file(upload_file), replace, is_async, skip_orm


@login_and_domain_required
def fixture_metadata(request, domain):
    """
    Returns list of fixtures and metadata needed for itemsets in vellum
    """
    return json_response(item_lists_by_domain(domain))
