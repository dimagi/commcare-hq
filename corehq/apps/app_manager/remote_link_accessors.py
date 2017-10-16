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


def get_remote_version(base_url, domain, app_id, auth):
    url = u'%s%s' % (base_url, reverse('current_app_version', args=[domain, app_id]))
    response = requests.get(url, auth=ApiKeyAuth(auth.username, auth.api_key))
    response.raise_for_status()
    return response.json().get('latestReleasedBuild')


def get_remote_master_release(base_url, domain, app_id, auth, linked_domain):
    # TODO also pull multimedia
    url = u'%s%s' % (base_url, reverse('latest_released_app_source', args=[domain, app_id]))
    requesting_authority = absolute_reverse('domain_homepage', args=[linked_domain])
    response = requests.get(
        url,
        params={'requester': requesting_authority},
        auth=ApiKeyAuth(auth.username, auth.api_key)
    )
    response.raise_for_status()
    app_json = response.json()
    return wrap_app(app_json)
