from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.case_importer.tracking.permissions import user_may_view_file_upload, \
    user_may_update_comment
from corehq.apps.case_importer.tracking.task_status import TaskStatus
from corehq.apps.users.dbaccessors.couch_users import get_display_name_for_user_id
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_request
from dimagi.ext import jsonobject


class CaseUploadJSON(jsonobject.StrictJsonObject):
    domain = jsonobject.StringProperty(required=True)
    # In user display format, e.g. Dec 08, 2016 19:19 EST
    created = jsonobject.StringProperty(required=True)
    upload_id = jsonobject.StringProperty(required=True)
    task_status = jsonobject.ObjectProperty(lambda: TaskStatus)
    user_name = jsonobject.StringProperty(required=True)
    case_type = jsonobject.StringProperty(required=True)
    comment = jsonobject.StringProperty()

    upload_file_name = jsonobject.StringProperty()
    upload_file_length = jsonobject.IntegerProperty()
    upload_file_download_allowed = jsonobject.BooleanProperty(required=True)
    upload_comment_edit_allowed = jsonobject.BooleanProperty(required=True)


def case_upload_to_user_json(case_upload, request):
    domain = case_upload.domain
    tz = get_timezone_for_request(request)

    return CaseUploadJSON(
        domain=case_upload.domain,
        created=ServerTime(case_upload.created).user_time(tz).ui_string(),
        upload_id=str(case_upload.upload_id),
        task_status=case_upload.get_task_status_json(),
        user_name=get_display_name_for_user_id(
            domain, case_upload.couch_user_id, default=''),
        case_type=case_upload.case_type,
        comment=case_upload.comment,
        upload_file_name=(case_upload.upload_file_meta.filename
                          if case_upload.upload_file_meta else None),
        upload_file_length=(case_upload.upload_file_meta.length
                            if case_upload.upload_file_meta else None),
        upload_file_download_allowed=user_may_view_file_upload(
            domain, request.couch_user, case_upload),
        upload_comment_edit_allowed=user_may_update_comment(
            request.couch_user, case_upload),
    )
