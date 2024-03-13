import ssl
from corehq.messaging.smsbackends.http.models import SQLHttpBackend


class SQLSislogBackend(SQLHttpBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'SISLOG'

    @classmethod
    def get_generic_name(cls):
        return "Sislog"

    @staticmethod
    def _encode_http_message(text):
        return text.encode("utf-8")

    @property
    def extra_urlopen_kwargs(self):
        return {'context': ssl._create_unverified_context()}
