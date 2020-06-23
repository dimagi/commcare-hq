from django.urls.base import reverse

import requests
from requests import ConnectionError

from dimagi.utils.logging import notify_exception

from corehq.apps.app_manager.dbaccessors import wrap_app
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.linked_domain.auth import ApiKeyAuth
from corehq.apps.linked_domain.exceptions import (
    ActionNotPermitted,
    RemoteAuthError,
    RemoteRequestError,
)
from corehq.util.view_utils import absolute_reverse


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


def get_brief_apps(domain_link):
    apps = _do_simple_request('linked_domain:brief_apps', domain_link)['brief_apps']
    return [wrap_app(app) for app in apps]


def get_app_by_version(domain_link, upstream_app_id, upstream_version):
    url = reverse('linked_domain:app_by_version', args=[domain_link.master_domain,
                                                        upstream_app_id,
                                                        upstream_version])
    response = _do_request_to_remote_hq_json(url, domain_link.remote_details, domain_link.linked_domain)
    return response['app']


def get_case_search_config(domain_link):
    return _do_simple_request('linked_domain:case_search_config', domain_link)


def get_released_app(master_domain, app_id, linked_domain, remote_details):
    url = reverse('linked_domain:latest_released_app_source', args=[master_domain, app_id])
    response = _do_request_to_remote_hq_json(url, remote_details, linked_domain)
    return _convert_app_from_remote_linking_source(response)


def get_latest_released_versions_by_app_id(domain_link):
    return _do_simple_request('linked_domain:released_app_versions', domain_link)['versions']


def get_ucr_config(domain_link, report_config_id):
    from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration
    url = reverse('linked_domain:ucr_config', args=[domain_link.master_domain,
                                                    report_config_id])
    response = _do_request_to_remote_hq_json(url, domain_link.remote_details, domain_link.linked_domain)
    return {
        "report": ReportConfiguration.wrap(response["report"]),
        "datasource": DataSourceConfiguration.wrap(response["datasource"]),
    }


def _convert_app_from_remote_linking_source(app_json):
    attachments = app_json.pop('_LAZY_ATTACHMENTS', {})
    app = wrap_app(app_json)
    app._LAZY_ATTACHMENTS = attachments
    return app


def fetch_remote_media(local_domain, missing_media, remote_app_details):
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
