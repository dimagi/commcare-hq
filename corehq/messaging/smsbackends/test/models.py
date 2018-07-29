from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.forms import BackendForm
from time import sleep


class SQLTestSMSBackend(SQLSMSBackend):

    class Meta(object):
        app_label = 'sms'
        proxy = True

    @classmethod
    def get_available_extra_fields(cls):
        return []

    @classmethod
    def get_api_id(cls):
        return 'TEST'

    @classmethod
    def get_generic_name(cls):
        return "Test"

    @classmethod
    def get_form_class(cls):
        return BackendForm

    def send(self, msg, *args, **kwargs):
        debug = getattr(settings, 'DEBUG', False)
        if debug:
            print("***************************************************")
            print("Message To:      %s" % msg.phone_number)
            print("Message Content: %s" % msg.text)
            print("***************************************************")

            # Simulate latency
            sleep(1)
