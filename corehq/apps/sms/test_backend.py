from django.conf import settings
from corehq.apps.sms.mixin import SMSBackend

class TestSMSBackend(SMSBackend):

    @classmethod
    def get_api_id(cls):
        return "TEST"

    def send(msg, *args, **kwargs):
        debug = getattr(settings, "DEBUG", False)
        if debug:
            print "***************************************************"
            print "Message To:      " + msg.phone_number
            print "Message Content: " + msg.text
            print "***************************************************"

