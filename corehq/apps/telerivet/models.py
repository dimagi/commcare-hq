import os
import requests
from couchdbkit.ext.django.schema import *
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.telerivet.forms import TelerivetBackendForm

MESSAGE_TYPE_SMS = "sms"


class TelerivetBackend(SMSBackend):
    # The api key of the account to send from.
    api_key = StringProperty()
    # The Telerivet project id.
    project_id = StringProperty()
    # The id of the phone to send from, as shown on Telerivet's API page.
    phone_id = StringProperty()
    # The Webhook Secret that gets posted to hq on every request
    webhook_secret = StringProperty()

    class Meta:
        app_label = "telerivet"

    @classmethod
    def get_api_id(cls):
        return "TELERIVET"

    @classmethod
    def get_generic_name(cls):
        return "Telerivet (Android)"

    @classmethod
    def get_template(cls):
        return "telerivet/backend.html"

    @classmethod
    def get_form_class(cls):
        return TelerivetBackendForm

    def send(self, msg, *args, **kwargs):
        text = msg.text.encode("utf-8")
        params = {
            "phone_id": str(self.phone_id),
            "to_number": clean_phone_number(msg.phone_number),
            "content": text,
            "message_type": MESSAGE_TYPE_SMS,
        }
        url = "https://api.telerivet.com/v1/projects/%s/messages/outgoing" % str(self.project_id)

        result = requests.post(
            url,
            auth=(str(self.api_key), ''),
            data=params,
            verify=True,
        )

        result = result.json()

    @classmethod
    def by_webhook_secret(cls, webhook_secret):
        return cls.view("telerivet/backend_by_secret", key=[webhook_secret],
                        include_docs=True).one()
