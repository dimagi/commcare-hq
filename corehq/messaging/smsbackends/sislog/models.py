from corehq.messaging.smsbackends.http.models import SQLHttpBackend


class SQLSislogBackend(SQLHttpBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'SISLOG'

    @classmethod
    def get_generic_name(cls):
        return "Sislog"
