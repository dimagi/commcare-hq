from __future__ import absolute_import
import os
from celery.task import task
from dropbox import Dropbox
from dropbox.files import UploadSessionCursor, CommitInfo, WriteMode
from dropbox.sharing import SharedLinkSettings, RequestedVisibility

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.users.models import CouchUser
from corehq.util.translation import localize
from corehq.util.log import send_HTML_email

CHUNK_SIZE = 5000000  # Read file in 5 MB chunks


@task
def upload(dropbox_helper_id, access_token, size, max_retries):
    from .models import DropboxUploadHelper
    helper = DropboxUploadHelper.objects.get(id=dropbox_helper_id)
    dbx = Dropbox(access_token)

    try:
        with open(helper.src, 'rb') as f:
            chunk = f.read(CHUNK_SIZE)
            offset = len(chunk)

            upload_session = dbx.files_upload_session_start(chunk)

            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                helper.progress = offset / size
                helper.save()
                dbx.files_upload_session_append_v2(
                    chunk,
                    UploadSessionCursor(
                        upload_session.session_id,
                        offset,
                    ),
                )
                offset += len(chunk)

            file_metadata = dbx.files_upload_session_finish(
                b'',
                UploadSessionCursor(
                    upload_session.session_id,
                    offset=offset,
                ),
                CommitInfo(
                    '/{}'.format(os.path.basename(helper.src)),
                    # When writing the file it won't overwrite an existing file, just add
                    # another file like "filename (2).txt"
                    WriteMode('add'),
                ),
            )
    except Exception as e:
        helper.failure_reason = str(e)
        helper.save()

    couch_user = CouchUser.get_by_username(helper.user.username)
    if helper.failure_reason is None:
        path_link_metadata = dbx.sharing_create_shared_link_with_settings(
            file_metadata.path_display,
            SharedLinkSettings(
                requested_visibility=RequestedVisibility.team_only,
            ),
        )
        context = {
            'share_url': path_link_metadata.url,
            'path': os.path.join(
                u'Apps',
                settings.DROPBOX_APP_NAME,
                path_link_metadata.name,
            )
        }
        with localize(couch_user.get_language_code()):
            subject = _(u'{} has been uploaded to dropbox!'.format(helper.dest))
            html_content = render_to_string('dropbox/emails/upload_success.html', context)
            text_content = render_to_string('dropbox/emails/upload_success.txt', context)
    else:
        context = {
            'reason': helper.failure_reason,
            'path': helper.dest
        }
        with localize(couch_user.get_language_code()):
            subject = _(u'{} has failed to upload to dropbox'.format(helper.dest))
            html_content = render_to_string('dropbox/emails/upload_error.html', context)
            text_content = render_to_string('dropbox/emails/upload_error.txt', context)

    send_HTML_email(
        subject,
        helper.user.email,
        html_content,
        text_content=text_content,
    )
