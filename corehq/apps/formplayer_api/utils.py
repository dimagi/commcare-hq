from django.conf import settings
from dimagi.utils.web import get_url_base


def get_formplayer_url():
    formplayer_url = settings.FORMPLAYER_URL
    if not formplayer_url.startswith('http'):
        formplayer_url = '{}{}'.format(get_url_base(), formplayer_url)
    return formplayer_url
