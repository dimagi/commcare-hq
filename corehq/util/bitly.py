from django.conf import settings

import requests
from requests import HTTPError


class BitlyError(Exception):

    def __init__(self, status_code, status_txt):
        self.status_code = status_code
        self.status_txt = status_txt

    def __str__(self):
        return "Bitly Error %s: %s" % (self.status_code, self.status_txt)


def shorten(url):
    if not getattr(settings, 'BITLY_OAUTH_TOKEN', None):
        return None

    response = requests.post("https://api-ssl.bitly.com/v4/shorten", json={"long_url": url}, headers={
        'Authorization': f'Bearer {settings.BITLY_OAUTH_TOKEN}',
        'Content-Type': 'application/json'
    })
    data = response.json()
    try:
        response.raise_for_status()
    except HTTPError:
        raise BitlyError(response.status_code, data.get('description', 'unknown'))
    return data['link']
