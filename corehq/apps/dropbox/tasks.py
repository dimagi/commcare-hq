from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import os
from celery.task import task
from dropbox import Dropbox
from dropbox.sharing import SharedLinkSettings, RequestedVisibility

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.dropbox.utils import upload_to_dropbox
from corehq.apps.users.models import CouchUser
from corehq.util.translation import localize
from corehq.util.log import send_HTML_email


@task(serializer='pickle')
def upload(dropbox_helper_id, access_token, size, max_retries):
    from .models import DropboxUploadHelper
    helper = DropboxUploadHelper.objects.get(id=dropbox_helper_id)

    def progress_callback(bytes_uploaded, helper=helper, size=size):
        helper.progress = float(bytes_uploaded) / size
        helper.save()

    try:
        dropbox_path = '/{}'.format(helper.dest)
        path_display = upload_to_dropbox(access_token, dropbox_path, helper.src, progress_callback)
    except Exception as e:
        helper.failure_reason = str(e)
        helper.save()

    couch_user = CouchUser.get_by_username(helper.user.username)
    if helper.failure_reason is None:
        dbx = Dropbox(access_token)
        path_link_metadata = dbx.sharing_create_shared_link_with_settings(
            path_display,
            SharedLinkSettings(
                requested_visibility=RequestedVisibility.team_only,
            ),
        )
        context = {
            'share_url': path_link_metadata.url,
            'path': os.path.join(
                'Apps',
                settings.DROPBOX_APP_NAME,
                path_link_metadata.name,
            )
        }
        with localize(couch_user.get_language_code()):
            subject = _('{} has been uploaded to dropbox!'.format(helper.dest))
            html_content = render_to_string('dropbox/emails/upload_success.html', context)
            text_content = render_to_string('dropbox/emails/upload_success.txt', context)
    else:
        context = {
            'reason': helper.failure_reason,
            'path': helper.dest
        }
        with localize(couch_user.get_language_code()):
            subject = _('{} has failed to upload to dropbox'.format(helper.dest))
            html_content = render_to_string('dropbox/emails/upload_error.html', context)
            text_content = render_to_string('dropbox/emails/upload_error.txt', context)

    send_HTML_email(
        subject,
        helper.user.email,
        html_content,
        text_content=text_content,
    )
