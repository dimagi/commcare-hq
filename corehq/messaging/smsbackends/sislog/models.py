from corehq.messaging.smsbackends.http.models import SQLHttpBackend


class SQLSislogBackend(SQLHttpBackend):
    class Meta:
        app_label = 'sms'
        proxy = True
