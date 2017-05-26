from corehq.messaging.smsbackends.http.models import SQLSMSBackend
from corehq.messaging.smsbackends.vertex.forms import VertexBackendForm


class SQLVertexBackend(SQLSMSBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_api_id(cls):
        return 'Vertex'

    @classmethod
    def get_generic_name(cls):
        return "Vertex"

    @classmethod
    def get_available_extra_fields(self):
        return [
            'username',
            'password',
            'senderid',
            'response',
        ]

    @classmethod
    def get_form_class(self):
        return VertexBackendForm
