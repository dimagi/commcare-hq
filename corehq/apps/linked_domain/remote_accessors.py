from __future__ import absolute_import
from __future__ import unicode_literals
import requests
import json
from couchdbkit.exceptions import ResourceNotFound
from django.urls.base import reverse
from requests import ConnectionError

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.app_manager.exceptions import MultimediaMissingError
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.linked_domain.auth import ApiKeyAuth
from corehq.apps.linked_domain.exceptions import RemoteRequestError, RemoteAuthError, ActionNotPermitted
from corehq.util.view_utils import absolute_reverse
from corehq.util.soft_assert import soft_assert
from dimagi.utils.logging import notify_exception
from django.utils.translation import ugettext as _


def get_toggles_previews(domain_link):
    return _do_simple_request('linked_domain:toggles', domain_link)


def get_custom_data_models(domain_link, limit_types=None):
    url = reverse('linked_domain:custom_data_models', args=[domain_link.master_domain])
    params = None
    if limit_types:
        params = [('type', type_) for type_ in limit_types]
    return _do_request_to_remote_hq_json(url, domain_link.remote_details, domain_link.linked_domain, params)


def get_user_roles(domain_link):
    return _do_simple_request('linked_domain:user_roles', domain_link)['user_roles']


def get_case_search_config(domain_link):
    return _do_simple_request('linked_domain:case_search_config', domain_link)


def get_released_app_version(master_domain, app_id, remote_details):
    url = reverse('current_app_version', args=[master_domain, app_id])
    response = _do_request_to_remote_hq_json(url, remote_details, None)
    return response.get('latestReleasedBuild')


def get_released_app(master_domain, app_id, linked_domain, remote_details):
    url = reverse('linked_domain:latest_released_app_source', args=[master_domain, app_id])
    response = _do_request_to_remote_hq_json(url, remote_details, linked_domain)
    return _convert_app_from_remote_linking_source(response)


def _convert_app_from_remote_linking_source(app_json):
    attachments = app_json.pop('_LAZY_ATTACHMENTS', {})
    app = wrap_app(app_json)
    app._LAZY_ATTACHMENTS = attachments
    return app


def pull_missing_multimedia_for_app(app, old_multimedia_ids=None):
    missing_media = _get_missing_multimedia(app, old_multimedia_ids)
    remote_details = app.domain_link.remote_details
    _fetch_remote_media(app.domain, missing_media, remote_details)
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
    response = _do_request_to_remote_hq(url, remote_app_details, None)
    return response.content


def _do_simple_request(url_name, domain_link):
    url = reverse(url_name, args=[domain_link.master_domain])
    return _do_request_to_remote_hq_json(url, domain_link.remote_details, domain_link.linked_domain)


def _do_request_to_remote_hq_json(relative_url, remote_details, linked_domain, params=None, method='get'):
    return _do_request_to_remote_hq(relative_url, remote_details, linked_domain, params, method).json()


def _do_request_to_remote_hq(relative_url, remote_details, linked_domain, params=None, method='get'):
    """
    :param relative_url: Relative URL on remote HQ
    :param remote_details: RemoteDetails object containing remote URL base and auth details
    :param linked_domain: Used for permission check on remote system
    :param params: GET/POST params to include
    :param method:
    :return:
    """
    url_base = remote_details.url_base
    username = remote_details.username
    api_key = remote_details.api_key
    full_url = '%s%s' % (url_base, relative_url)
    headers = {
        'HQ-REMOTE-REQUESTER': absolute_reverse('domain_homepage', args=[linked_domain])
    }
    try:
        response = requests.request(
            method, full_url,
            params=params, auth=ApiKeyAuth(username, api_key), headers=headers
        )
    except ConnectionError:
        notify_exception(None, "Error performing remote app request", details={
            'remote_url': full_url,
            'params': params,
            'headers': headers
        })
        raise RemoteRequestError()
    if response.status_code == 401:
        raise RemoteAuthError(response.status_code)
    elif response.status_code == 403:
        raise ActionNotPermitted(response.status_code)
    elif response.status_code != 200:
        notify_exception(None, "Error performing remote app request", details={
            'remote_url': full_url,
            'response_code': response.status_code,
            'params': params
        })
        raise RemoteRequestError(response.status_code)
    return response
