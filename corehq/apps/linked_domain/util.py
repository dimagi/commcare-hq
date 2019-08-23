from __future__ import absolute_import

from __future__ import unicode_literals

import six
from couchdbkit import ResourceNotFound
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.exceptions import MultimediaMissingError
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.linked_domain.remote_accessors import fetch_remote_media
from corehq.util.timezones.conversions import ServerTime


def _clean_json(doc):
    if not isinstance(doc, dict):
        return doc
    doc.pop('domain', None)
    doc.pop('doc_type', None)
    doc.pop('_id', None)
    doc.pop('_rev', None)
    for key, val in doc.items():
        if isinstance(val, dict):
            _clean_json(val)
        if isinstance(val, list):
            [_clean_json(inner_doc) for inner_doc in val]
    return doc


def convert_app_for_remote_linking(latest_master_build):
    _attachments = latest_master_build.get_attachments()
    source = latest_master_build.to_json()
    source['_LAZY_ATTACHMENTS'] = {
        name: {'content': content.decode('utf-8')}
        for name, content in _attachments.items()
    }
    source.pop("external_blobs", None)
    return source


def server_to_user_time(server_time, timezone):
    user_time = ServerTime(server_time).user_time(timezone).done()
    return user_time.strftime("%Y-%m-%d %H:%M")


def pull_missing_multimedia_for_app_and_notify(domain, app_id, email):
    app = get_app(domain, app_id)
    subject = _("Update Status for linked app %s missing multimedia pull") % app.name
    try:
        pull_missing_multimedia_for_app(app)
    except MultimediaMissingError as e:
        message = six.text_type(e)
    except Exception:
        # Send an email but then crash the process
        # so we know what the error was
        send_html_email_async.delay(subject, email, _(
            "Something went wrong while pulling multimedia for your linked app. "
            "Our team has been notified and will monitor the situation. "
            "Please try again, and if the problem persists report it as an issue."))
        raise
    else:
        message = _("Multimedia was successfully updated for the linked app.")
    send_html_email_async.delay(subject, email, message)


def pull_missing_multimedia_for_app(app, old_multimedia_ids=None):
    missing_media = _get_missing_multimedia(app, old_multimedia_ids)
    remote_details = app.domain_link.remote_details
    fetch_remote_media(app.domain, missing_media, remote_details)
    if toggles.CAUTIOUS_MULTIMEDIA.enabled(app.domain):
        still_missing_media = _get_missing_multimedia(app, old_multimedia_ids)
        if still_missing_media:
            raise MultimediaMissingError(_(
                'Application has missing multimedia even after an attempt to re-pull them. '
                'Please try re-pulling the app. If this persists, report an issue.'
            ))


def _get_missing_multimedia(app, old_multimedia_ids=None):
    missing = []
    for path, media_info in app.multimedia_map.items():
        if old_multimedia_ids and media_info['multimedia_id'] in old_multimedia_ids:
            continue
        try:
            local_media = CommCareMultimedia.get(media_info['multimedia_id'])
        except ResourceNotFound:
            filename = path.split('/')[-1]
            missing.append((filename, media_info))
        else:
            _add_domain_access(app.domain, local_media)
    return missing


def _add_domain_access(domain, media):
    if domain not in media.valid_domains:
        media.add_domain(domain)
