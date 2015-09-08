from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.sms.mixin import MobileBackend
from corehq.messaging.smsbackends.mach.api import MachBackend
from corehq.messaging.smsbackends.unicel.api import UnicelBackend
from corehq.messaging.smsbackends.tropo.api import TropoBackend
from corehq.apps.sms.backend.http_api import HttpBackend
from corehq.apps.sms.test_backend import TestSMSBackend
from django.conf import settings
from couchdbkit.resource import ResourceNotFound
import re

class Command(BaseCommand):
    args = ""
    help = "Migrate backends to support backend refactor."

    # Migrate all backends
    def handle(self, *args, **options):
        backends = MobileBackend.view("sms/old_mobile_backend", include_docs=True).all()
        for backend in backends:
            print "Processing backend %s" % backend._id
            if backend._id == "MOBILE_BACKEND_UNICEL":
                backend = UnicelBackend.wrap(backend.to_json())
                backend.doc_type = "UnicelBackend"
                backend.domain = None
                backend.name = backend._id
                backend.authorized_domains = []
                backend.is_global = True
                backend.username = settings.UNICEL_CONFIG.get("username")
                backend.password = settings.UNICEL_CONFIG.get("password")
                backend.sender = settings.UNICEL_CONFIG.get("sender")
                backend.reply_to_phone_number = settings.UNICEL_CONFIG.get("receive_phone", None)
                backend.outbound_module = None
                backend.outbound_params = None
                backend.save()
            elif backend._id == "MOBILE_BACKEND_MACH":
                backend = MachBackend.wrap(backend.to_json())
                backend.doc_type = "MachBackend"
                backend.domain = None
                backend.name = backend._id
                backend.authorized_domains = []
                backend.is_global = True
                backend.account_id = re.match(r".*id=(.+?)&", settings.SMS_GATEWAY_PARAMS).group(1)
                backend.password = re.match(r".*pw=(.+?)&", settings.SMS_GATEWAY_PARAMS).group(1)
                backend.sender_id = "DIMAGI"
                backend.outbound_module = None
                backend.outbound_params = None
                backend.save()
            elif backend.outbound_module == "corehq.messaging.smsbackends.tropo.api":
                backend = TropoBackend.wrap(backend.to_json())
                backend.doc_type = "TropoBackend"
                backend.domain = None
                backend.name = backend._id
                backend.authorized_domains = []
                backend.is_global = True
                backend.messaging_token = backend.outbound_params.get("messaging_token")
                backend.outbound_module = None
                backend.outbound_params = None
                backend.save()
            elif backend.outbound_module == "corehq.apps.sms.backend.http_api":
                print "REMINDER: Need to set global / domain for backend %s" % backend._id
                backend = HttpBackend.wrap(backend.to_json())
                backend.doc_type = "HttpBackend"
                backend.domain = None
                backend.name = backend._id
                backend.authorized_domains = []
                backend.is_global = False
                backend.url = backend.outbound_params.get("url")
                backend.message_param = backend.outbound_params.get("message_param")
                backend.number_param = backend.outbound_params.get("number_param")
                backend.include_plus = backend.outbound_params.get("include_plus", False)
                backend.method = backend.outbound_params.get("method", "GET")
                backend.additional_params = backend.outbound_params.get("additional_params", {})
                backend.outbound_module = None
                backend.outbound_params = None
                backend.save()
            elif backend.outbound_module == "corehq.apps.sms.test_backend":
                backend = TestSMSBackend.wrap(backend.to_json())
                backend.doc_type = "TestSMSBackend"
                backend.domain = None
                backend.name = backend._id
                backend.authorized_domains = []
                backend.is_global = True
                backend.outbound_module = None
                backend.outbound_params = None
                backend.save()

    # If no unicel backend was present, create one
    try:
        MobileBackend.get("MOBILE_BACKEND_UNICEL")
    except ResourceNotFound:
        backend = UnicelBackend(
            domain = None,
            name = "MOBILE_BACKEND_UNICEL",
            authorized_domains = [],
            is_global = True,
            username = settings.UNICEL_CONFIG.get("username"),
            password = settings.UNICEL_CONFIG.get("password"),
            sender = settings.UNICEL_CONFIG.get("sender"),
            reply_to_phone_number = settings.UNICEL_CONFIG.get("receive_phone", None),
        )
        backend._id = backend.name
        backend.save()

    # If no mach backend was present, create one
    try:
        MobileBackend.get("MOBILE_BACKEND_MACH")
    except ResourceNotFound:
        backend = MachBackend(
            domain = None,
            name = "MOBILE_BACKEND_MACH",
            authorized_domains = [],
            is_global = True,
            account_id = re.match(r".*id=(.+?)&", settings.SMS_GATEWAY_PARAMS).group(1),
            password = re.match(r".*pw=(.+?)&", settings.SMS_GATEWAY_PARAMS).group(1),
            sender_id = "DIMAGI",
        )
        backend._id = backend.name
        backend.save()

    # If no test backend was present, create one
    try:
        MobileBackend.get("MOBILE_BACKEND_TEST")
    except ResourceNotFound:
        backend = TestSMSBackend(
            domain = None,
            name = "MOBILE_BACKEND_TEST",
            authorized_domains = [],
            is_global = True,
        )
        backend._id = backend.name
        backend.save()

