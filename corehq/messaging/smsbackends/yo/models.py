from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.messaging.smsbackends.http.models import SQLHttpBackend


class SQLYoBackend(SQLHttpBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'YO'

    @classmethod
    def get_generic_name(cls):
        return "Yo! Uganda"
