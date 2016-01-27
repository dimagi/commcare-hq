from django.conf import settings
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.sms.models import SQLSMSBackend
from corehq.apps.sms.forms import BackendForm

class TestSMSBackend(SMSBackend):

    @classmethod
    def get_api_id(cls):
        return "TEST"

    @classmethod
    def get_generic_name(cls):
        return "Test"

    @classmethod
    def get_form_class(cls):
        return BackendForm

    def send(self, msg, *args, **kwargs):
        debug = getattr(settings, "DEBUG", False)
        if debug:
            print "***************************************************"
            print "Message To:      %s" % msg.phone_number
            print "Message Content: %s" % msg.text
            print "***************************************************"

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLTestSMSBackend


class SQLTestSMSBackend(SQLSMSBackend):
    class Meta:
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
            print "***************************************************"
            print "Message To:      %s" % msg.phone_number
            print "Message Content: %s" % msg.text
            print "***************************************************"
