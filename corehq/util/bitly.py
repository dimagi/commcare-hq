from django.conf import settings
from urllib2 import urlopen
import simplejson

class BitlyError(Exception):
    def __init__(self, status_code, status_txt):
        self.status_code = status_code
        self.status_txt = status_txt
    def __str__(self):
        return "Bitly Error %s: %s" % self.status_code, self.status_txt

def shorten(url, login=settings.BITLY_LOGIN, api_key=settings.BITLY_APIKEY):
    json = simplejson.load(
        urlopen("http://api.bit.ly/v3/shorten?login=%s&apiKey=%s&longUrl=%s" % (login, api_key, url))
    )
    if not json['data']:
        raise BitlyError(json['status_code'], json['status_txt'])
    return json['data']['url']