from __future__ import absolute_import, unicode_literals

from io import open

from django.db import transaction
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    StreamingHttpResponse,
)

from dimagi.utils.web import json_response

from corehq.apps.case_importer.base import locsafe_imports_enabled
from corehq.apps.case_importer.tracking.dbaccessors import (
    get_case_ids_for_case_upload,
    get_case_upload_records,
    get_form_ids_for_case_upload,
)
from corehq.apps.case_importer.tracking.jsmodels import (
    case_upload_to_user_json,
)
from corehq.apps.case_importer.tracking.models import (
    MAX_COMMENT_LENGTH,
    CaseUploadRecord,
)
from corehq.apps.case_importer.tracking.permissions import (
    user_may_update_comment,
    user_may_view_file_upload,
)
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.locations.permissions import conditionally_location_safe
from corehq.util.view_utils import set_file_download


@require_can_edit_data
@conditionally_location_safe(locsafe_imports_enabled)
def case_uploads(request, domain):
    try:
        limit = int(request.GET.get('limit'))
    except (TypeError, ValueError):
        limit = 10

    try:
        page = int(request.GET.get('page'))
    except (TypeError, ValueError):
        page = 1

    case_upload_records = get_case_upload_records(domain, request.couch_user, limit, skip=limit * (page - 1))

    with transaction.atomic():
        for case_upload_record in case_upload_records:
            if case_upload_record.set_task_status_json_if_finished():
                case_upload_record.save()

    case_uploads_json = [case_upload_to_user_json(case_upload_record, request)
                         for case_upload_record in case_upload_records]

    return json_response(case_uploads_json)


@require_can_edit_data
@conditionally_location_safe(locsafe_imports_enabled)
def update_case_upload_comment(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    if not user_may_update_comment(request.couch_user, case_upload):
        return HttpResponseForbidden()

    comment = request.POST.get('comment')
    if comment is None:
        return HttpResponseBadRequest("POST body must contain non-null comment property")
    elif len(comment) > MAX_COMMENT_LENGTH:
        return HttpResponseBadRequest("comment must be shorter than {} characters"
                                      .format(MAX_COMMENT_LENGTH))

    case_upload.comment = comment
    case_upload.save()
    return json_response({})


@require_can_edit_data
@conditionally_location_safe(locsafe_imports_enabled)
def case_upload_file(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    if not user_may_view_file_upload(domain, request.couch_user, case_upload):
        return HttpResponseForbidden()

    response = StreamingHttpResponse(open(case_upload.get_tempfile_ref_for_upload_ref(), 'rb'))

    set_file_download(response, case_upload.upload_file_meta.filename)
    return response


@require_can_edit_data
@conditionally_location_safe(locsafe_imports_enabled)
def case_upload_form_ids(request, domain, upload_id):
    try:
        case_upload = _get_case_upload_record(domain, upload_id, request.couch_user)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    ids_stream = ('{}\n'.format(form_id)
                  for form_id in get_form_ids_for_case_upload(case_upload))

    return StreamingHttpResponse(ids_stream, content_type='text/plain')


@require_can_edit_data
@conditionally_location_safe(locsafe_imports_enabled)
def case_upload_case_ids(request, domain, upload_id):
    try:
        case_upload = _get_case_upload_record(domain, upload_id, request.couch_user)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    ids_stream = ('{}\n'.format(case_id)
                  for case_id in get_case_ids_for_case_upload(case_upload))

    return StreamingHttpResponse(ids_stream, content_type='text/plain')


def _get_case_upload_record(domain, upload_id, user):
    kwargs = {
        'domain': domain,
        'upload_id': upload_id,
    }
    if not user.has_permission(domain, 'access_all_locations'):
        kwargs['couch_user_id'] = user._id
    return CaseUploadRecord.objects.get(**kwargs)
