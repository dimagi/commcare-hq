import requests
from django.urls.base import reverse
from requests.auth import AuthBase

from corehq.apps.app_manager.dbaccessors import wrap_app
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
    url_base, domain, username, api_key, app_id = remote_app_details
    url = u'%s%s' % (url_base, reverse('current_app_version', args=[domain, app_id]))
    response = requests.get(url, auth=ApiKeyAuth(username, api_key))
    response.raise_for_status()
    return response.json().get('latestReleasedBuild')


def get_remote_master_release(remote_app_details, linked_domain):
    # TODO also pull multimedia
    url_base, domain, username, api_key, app_id = remote_app_details
    url = u'%s%s' % (url_base, reverse('latest_released_app_source', args=[domain, app_id]))
    requesting_authority = absolute_reverse('domain_homepage', args=[linked_domain])
    response = requests.get(
        url,
        params={'requester': requesting_authority},
        auth=ApiKeyAuth(username, api_key)
    )
    response.raise_for_status()
    app_json = response.json()
    return _convert_app_from_remote_linking_source(app_json)


def _convert_app_from_remote_linking_source(app_json):
    attachments = app_json.pop('_LAZY_ATTACHMENTS', {})
    app = wrap_app(app_json)
    app._LAZY_ATTACHMENTS = attachments
    return app
