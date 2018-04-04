from __future__ import absolute_import

from __future__ import unicode_literals
from dropbox import Dropbox
from dropbox.files import UploadSessionCursor, CommitInfo, WriteMode
from dropbox.oauth import DropboxOAuth2Flow

from django.conf import settings
from django.urls import reverse

from dimagi.utils.web import get_url_base


DROPBOX_CSRF_TOKEN = 'dropbox-auth-csrf-token'
CHUNK_SIZE = 5000000  # Read file in 5 MB chunks


def get_dropbox_auth_flow(session):
    from .views import DropboxAuthCallback

    redirect_uri = '{}{}'.format(
        get_url_base(),
        reverse(DropboxAuthCallback.slug),
    )
    return DropboxOAuth2Flow(
        settings.DROPBOX_KEY,
        settings.DROPBOX_SECRET,
        redirect_uri,
        session,
        DROPBOX_CSRF_TOKEN
    )


def upload_to_dropbox(access_token, dropbox_path, file_path, progress_callback=None):
    dbx = Dropbox(access_token)
    with open(file_path, 'rb') as file:
        chunk = file.read(CHUNK_SIZE)
        offset = len(chunk)

        upload_session = dbx.files_upload_session_start(chunk)
        progress_callback and progress_callback(offset)

        while True:
            chunk = file.read(CHUNK_SIZE)
            if not chunk:
                break
            dbx.files_upload_session_append_v2(
                chunk,
                UploadSessionCursor(
                    upload_session.session_id,
                    offset,
                ),
            )
            offset += len(chunk)
            progress_callback and progress_callback(offset)

        file_metadata = dbx.files_upload_session_finish(
            b'',
            UploadSessionCursor(
                upload_session.session_id,
                offset=offset,
            ),
            CommitInfo(
                dropbox_path,
                # When writing the file it won't overwrite an existing file, just add
                # another file like "filename (2).txt"
                WriteMode('add'),
            ),
        )
        progress_callback and progress_callback(offset)
        return file_metadata.path_display
