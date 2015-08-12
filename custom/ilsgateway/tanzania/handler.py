import re
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize

from custom.ilsgateway.tanzania.handlers.arrived import ArrivedHandler
from custom.ilsgateway.tanzania.handlers.delivered import DeliveredHandler
from custom.ilsgateway.tanzania.handlers.help import HelpHandler
from custom.ilsgateway.tanzania.handlers.la import LossAndAdjustment
from custom.ilsgateway.tanzania.handlers.language import LanguageHandler
from custom.ilsgateway.tanzania.handlers.messageinitiator import MessageInitiatior
from custom.ilsgateway.tanzania.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.tanzania.handlers.notsubmitted import NotSubmittedHandler
from custom.ilsgateway.tanzania.handlers.register import RegisterHandler
from custom.ilsgateway.tanzania.handlers.soh import SOHHandler
from custom.ilsgateway.tanzania.handlers.stop import StopHandler
from custom.ilsgateway.tanzania.handlers.supervision import SupervisionHandler
from custom.ilsgateway.tanzania.handlers.randr import RandrHandler
from custom.ilsgateway.tanzania.handlers.yes import YesHandler
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.reminders import CONTACT_SUPERVISOR


def handle(verified_contact, text, msg=None):
    user = verified_contact.owner if verified_contact else None
    domain = user.domain

    if domain and not ILSGatewayConfig.for_domain(domain):
        return False

    args = text.split()
    if not args:
        return False
    keyword = args[0]
    args = args[1:]
    params = {
        'user': user,
        'domain': domain,
        'args': args,
        'msg': msg,
        'verified_contact': verified_contact
    }

    def not_function(word):
        if args and re.match("del", word):
            return NotDeliveredHandler
        elif args and re.match("sub", word):
            return NotSubmittedHandler
        return None

    handlers = {
        ('soh', 'hmk'): SOHHandler,
        ('submitted', 'nimetuma'): RandrHandler,
        ('delivered', 'dlvd', 'nimepokea'): DeliveredHandler,
        ('sijapokea',): NotDeliveredHandler,
        ('sijatuma',): NotSubmittedHandler,
        ('supervision', 'usimamizi'): SupervisionHandler,
        ('arrived', 'aliwasili'): ArrivedHandler,
        ('help', 'msaada'): HelpHandler,
        ('language', 'lang', 'lugha'): LanguageHandler,
        ('stop', 'acha', 'hapo'): StopHandler,
        ('yes', 'ndio', 'ndyo'): YesHandler,
        ('la', 'um'): LossAndAdjustment,
        ('register', 'reg', 'join', 'sajili'): RegisterHandler,
        ('test',): MessageInitiatior,
        ('not',): not_function(args[0]) if args else None
    }

    def choose_handler(keyword):
        for k, v in handlers.iteritems():
            if keyword.lower() in k:
                return v
        return None

    handler_class = choose_handler(keyword)
    handler = handler_class(**params) if handler_class else None

    if handler:
        if args:
            return handler.handle()
        else:
            return handler.help()
    elif keyword != 'l':
        with localize(verified_contact.owner.get_language_code()):
            send_sms_to_verified_number(verified_contact, unicode(CONTACT_SUPERVISOR))
        return True
