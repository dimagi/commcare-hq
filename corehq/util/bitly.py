from __future__ import absolute_import
from django.conf import settings
from six.moves.urllib.request import urlopen
import json


class BitlyError(Exception):

    def __init__(self, status_code, status_txt):
        self.status_code = status_code
        self.status_txt = status_txt

    def __str__(self):
        return "Bitly Error %s: %s" % (self.status_code, self.status_txt)


def shorten(url, login=settings.BITLY_LOGIN, api_key=settings.BITLY_APIKEY):
    response = json.load(
        urlopen("http://api.bit.ly/v3/shorten?login=%s&apiKey=%s&longUrl=%s" % (login, api_key, url))
    )
    if not response['data']:
        raise BitlyError(response['status_code'], response['status_txt'])
    return response['data']['url']
