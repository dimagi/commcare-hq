from corehq.messaging.smsbackends.http.models import SQLHttpBackend


class SQLYoBackend(SQLHttpBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'YO'
