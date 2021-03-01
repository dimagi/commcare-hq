from django.conf import settings

from corehq.apps.formplayer_api.exceptions import FormplayerAPIException
from dimagi.utils.web import get_url_base


def get_formplayer_url():
    formplayer_url = settings.FORMPLAYER_URL
    if not formplayer_url.startswith('http'):
        formplayer_url = '{}{}'.format(get_url_base(), formplayer_url)
    return formplayer_url


def check_user_access(domain, username, allow_mirroring=False):
    from corehq.apps.users.util import format_username
    from corehq.apps.users.models import CouchUser
    if '@' not in username:
        username = format_username(username, domain)
    user = CouchUser.get_by_username(username)
    if not user.is_member_of(domain, allow_mirroring=allow_mirroring):
        raise FormplayerAPIException(f"User '{username}' does not have access to domain '{domain}'")
    return user
