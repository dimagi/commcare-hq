from corehq.apps.sms.api import send_sms_to_verified_number


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
        send_sms_to_verified_number(self.verified_contact, message % kwargs)