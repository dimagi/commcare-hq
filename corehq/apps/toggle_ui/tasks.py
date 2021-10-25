import inspect
from datetime import datetime

import pytz
from celery.task import task
from django.conf import settings

from corehq.apps.toggle_ui.utils import get_toggles_attachment_file
from corehq.apps.users.models import CouchUser
from corehq.blobs import get_blob_db, CODES
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.files import safe_filename_header
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.django.email import send_HTML_email
from soil.util import expose_blob_download


@task(bind=True)
def generate_toggle_download(self, tag, download_id, username):
    timeout_mins = 24 * 60
    data = get_toggles_attachment_file(tag)
    db = get_blob_db()
    meta = db.put(
        data,
        domain="__system__",
        parent_id="__system__",
        type_code=CODES.tempfile,
        key=download_id,
        timeout=timeout_mins,
    )

    now = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    filename = f'{settings.SERVER_ENVIRONMENT}_toggle_export_{now}'
    expose_blob_download(
        download_id,
        expiry=timeout_mins * 60,
        content_disposition=safe_filename_header(filename, ".csv"),
        download_id=download_id,
    )

    user = CouchUser.get_by_username(username)
    if user:
        url = absolute_reverse("retrieve_download", args=[download_id])
        url += "?get_file"
        valid_until = meta.expires_on.replace(tzinfo=pytz.UTC).strftime(USER_DATETIME_FORMAT)
        send_HTML_email("Feature Flag download ready", user.get_email(), html_content=inspect.cleandoc(f"""
        Download URL: {url}
        Download Valid until: {valid_until}
        """))
