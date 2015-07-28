from celery.task import task
from dropbox.client import DropboxClient
from dropbox.rest import ErrorResponse

from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from corehq.apps.users.models import CouchUser
from corehq.util.translation import localize
from dimagi.utils.django.email import send_HTML_email


@task
def upload(dropbox_helper_id, access_token, size, max_retries):
    from .models import DropboxUploadHelper
    helper = DropboxUploadHelper.objects.get(id=dropbox_helper_id)
    client = DropboxClient(access_token)
    retries = 0

    try:
        with open(helper.src, 'rb') as f:
            uploader = client.get_chunked_uploader(f, size)
            while uploader.offset < size:
                helper.progress = uploader.offset / size
                helper.save()
                try:
                    uploader.upload_chunked()
                except ErrorResponse, e:
                    if retries < helper.max_retries:
                        retries += 1
                    else:
                        helper.failure_reason = str(e)
                        helper.save()
                        raise e

            upload = uploader.finish(helper.dest)
    except Exception, e:
        helper.failure_reason = str(e)
        helper.save()

    couch_user = CouchUser.get_by_username(helper.user.username)
    if helper.failure_reason is None:
        share = client.share(upload['path'])
        context = {
            'share_url': share.get('url', None),
            'path': upload['path']
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
