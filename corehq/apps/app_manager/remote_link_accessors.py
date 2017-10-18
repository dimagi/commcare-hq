import requests
from couchdbkit.exceptions import ResourceNotFound
from django.urls.base import reverse
from requests.auth import AuthBase

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.util.view_utils import absolute_reverse


class ApiKeyAuth(AuthBase):
    def __init__(self, username, apikey):
        self.username = username
        self.apikey = apikey

    def __eq__(self, other):
        return all([
            self.username == getattr(other, 'username', None),
            self.apikey == getattr(other, 'apikey', None)
        ])

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers['Authorization'] = 'apikey %s:%s' % (self.username, self.apikey)
        return r


def get_remote_version(remote_app_details):
    url = reverse('current_app_version', args=[remote_app_details.domain, remote_app_details.app_id])
    response = _do_request_to_remote_hq(url, remote_app_details)
    return response.json().get('latestReleasedBuild')


def get_remote_master_release(remote_app_details, linked_domain):
    url = reverse('latest_released_app_source', args=[remote_app_details.domain, remote_app_details.app_id])
    params = {'requester': absolute_reverse('domain_homepage', args=[linked_domain])}
    response = _do_request_to_remote_hq(url, remote_app_details, params)
    return _convert_app_from_remote_linking_source(response.json())


def _convert_app_from_remote_linking_source(app_json):
    attachments = app_json.pop('_LAZY_ATTACHMENTS', {})
    app = wrap_app(app_json)
    app._LAZY_ATTACHMENTS = attachments
    return app


def pull_missing_multimedia_from_remote(app):
    missing_media = _get_missing_multimedia(app)
    _fetch_remote_media(app.domain, missing_media, app.remote_app_details)


def _get_missing_multimedia(app):
    missing = []
    for media_info in app.multimedia_map.values():
        try:
            local_media = CommCareMultimedia.get(media_info['multimedia_id'])
        except ResourceNotFound:
            missing.append(media_info)
        else:
            _check_domain_access(app.domain, local_media)
    return missing


def _check_domain_access(domain, media):
    if domain not in media.valid_domains:
        media.add_domain(domain)


def _fetch_remote_media(local_domain, missing_media, remote_app_details):
    for item in missing_media:
        media_class = CommCareMultimedia.get_doc_class(item['media_type'])
        content = _fetch_remote_media_content(item['multimedia_id'], remote_app_details)
        media_item = media_class.get_by_data(content)
        media_item._id = item['multimedia_id']
        media_item.attach_data(content)
        media_item.add_domain(local_domain, owner=True)


def _fetch_remote_media_content(media_item_id, remote_app_details):
    url = reverse('??', args=[remote_app_details.domain, media_item_id])
    response = _do_request_to_remote_hq(url, remote_app_details)
    return response.content


def _do_request_to_remote_hq(relative_url, remote_app_details, params=None):
    url_base, domain, username, api_key, app_id = remote_app_details
    full_url = u'%s%s' % (url_base, relative_url)
    response = requests.get(full_url, params=params, auth=ApiKeyAuth(username, api_key))
    response.raise_for_status()
    return response
