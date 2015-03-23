from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from django.utils.translation import ugettext as _


class KeywordHandler(object):

    def __init__(self, user, domain, args, verified_contact, msg):
        self.user = user
        self.domain = domain
        self.args = args
        self.verified_contact = verified_contact
        self.msg = msg

    def handle(self):
        raise NotImplementedError("Not implemented yet")

    def help(self):
        raise NotImplementedError("Not implemented yet")

    def respond(self, message, **kwargs):
        owner = self.verified_contact.owner
        with localize(owner.get_language_code()):
            send_sms_to_verified_number(self.verified_contact, _(message) % kwargs)
