from __future__ import absolute_import
import requests
from couchdbkit.exceptions import ResourceNotFound
from django.urls.base import reverse
from requests import ConnectionError

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.exceptions import RemoteRequestError, RemoteAuthError, ActionNotPermitted
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.linked_domain.auth import ApiKeyAuth
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.logging import notify_exception


def get_released_app_version(remote_app_details):
    url = reverse('current_app_version', args=[remote_app_details.domain, remote_app_details.app_id])
    response = _do_request_to_remote_hq(url, remote_app_details)
    return response.json().get('latestReleasedBuild')


def get_released_app(remote_app_details, linked_domain):
    url = reverse('latest_released_app_source', args=[remote_app_details.domain, remote_app_details.app_id])
    params = {'requester': absolute_reverse('domain_homepage', args=[linked_domain])}
    response = _do_request_to_remote_hq(url, remote_app_details, params)
    return _convert_app_from_remote_linking_source(response.json())


def whilelist_app_on_remote(remote_app_details, linked_domain):
    url = reverse('patch_linked_app_whitelist', args=[remote_app_details.domain, remote_app_details.app_id])
    params = {'whitelist_item': absolute_reverse('domain_homepage', args=[linked_domain])}
    _do_request_to_remote_hq(url, remote_app_details, params, method='patch')


def _convert_app_from_remote_linking_source(app_json):
    attachments = app_json.pop('_LAZY_ATTACHMENTS', {})
    app = wrap_app(app_json)
    app._LAZY_ATTACHMENTS = attachments
    return app


def pull_missing_multimedia_for_app(app):
    missing_media = _get_missing_multimedia(app)
    _fetch_remote_media(app.domain, missing_media, app.remote_app_details)


def _get_missing_multimedia(app):
    missing = []
    for path, media_info in app.multimedia_map.items():
        try:
            local_media = CommCareMultimedia.get(media_info['multimedia_id'])
        except ResourceNotFound:
            filename = path.split('/')[-1]
            missing.append((filename, media_info))
        else:
            _check_domain_access(app.domain, local_media)
    return missing


def _check_domain_access(domain, media):
    if domain not in media.valid_domains:
        media.add_domain(domain)


def _fetch_remote_media(local_domain, missing_media, remote_app_details):
    for filename, item in missing_media:
        media_class = CommCareMultimedia.get_doc_class(item['media_type'])
        content = _fetch_remote_media_content(item, remote_app_details)
        media_item = media_class.get_by_data(content)
        media_item._id = item['multimedia_id']
        media_item.attach_data(content, original_filename=filename)
        media_item.add_domain(local_domain, owner=True)


def _fetch_remote_media_content(media_item, remote_app_details):
    url = reverse('hqmedia_download', args=[media_item['media_type'], media_item['multimedia_id']])
    response = _do_request_to_remote_hq(url, remote_app_details)
    return response.content


def _do_request_to_remote_hq(relative_url, remote_app_details, params=None, method='get'):
    url_base, domain, username, api_key, app_id = remote_app_details
    full_url = u'%s%s' % (url_base, relative_url)
    try:
        response = requests.request(method, full_url, params=params, auth=ApiKeyAuth(username, api_key))
    except ConnectionError:
        notify_exception(None, "Error performaing remote app request", details={
            'remote_url': full_url,
            'params': params
        })
        raise RemoteRequestError
    if response.status_code == 401:
        raise RemoteAuthError
    elif response.status_code == 403:
        raise ActionNotPermitted
    elif response.status_code != 200:
        notify_exception(None, "Error performaing remote app request", details={
            'remote_url': full_url,
            'response_code': response.status_code,
            'params': params
        })
        raise RemoteRequestError
    return response
