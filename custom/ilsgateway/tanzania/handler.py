import re
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from custom.ilsgateway.slab.handlers.transfer import TransferHandler

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
from custom.ilsgateway.tanzania.handlers.stockout import StockoutHandler
from custom.ilsgateway.tanzania.handlers.stop import StopHandler
from custom.ilsgateway.tanzania.handlers.supervision import SupervisionHandler
from custom.ilsgateway.tanzania.handlers.randr import RandrHandler
from custom.ilsgateway.tanzania.handlers.yes import YesHandler
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.reminders import CONTACT_SUPERVISOR


def choose_handler(keyword, handlers):
    for k, v in handlers.iteritems():
        if keyword.lower() in k:
            return v
    return None


def handle(verified_contact, text, msg=None):
    user = verified_contact.owner if verified_contact else None
    domain = user.domain

    if domain and not ILSGatewayConfig.for_domain(domain):
        return False

    text = text.replace('\r', ' ').replace('\n', ' ').strip()
    args = text.split()
    if not args:
        return False
    keyword = args[0]

    if keyword.startswith('#'):
        return False

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
        ('arrived', 'aliwasili'): ArrivedHandler,
        ('help', 'msaada'): HelpHandler,
        ('language', 'lang', 'lugha'): LanguageHandler,
        ('stop', 'acha', 'hapo'): StopHandler,
        ('yes', 'ndio', 'ndyo'): YesHandler,
        ('register', 'reg', 'join', 'sajili'): RegisterHandler,
        ('test',): MessageInitiatior,
    }

    location_needed_handlers = {
        ('soh', 'hmk'): SOHHandler,
        ('submitted', 'nimetuma'): RandrHandler,
        ('delivered', 'dlvd', 'nimepokea'): DeliveredHandler,
        ('sijapokea',): NotDeliveredHandler,
        ('sijatuma',): NotSubmittedHandler,
        ('supervision', 'usimamizi'): SupervisionHandler,
        ('la', 'um'): LossAndAdjustment,
        ('stockout', 'hakuna'): StockoutHandler,
        ('not',): not_function(args[0]) if args else None,
        ('trans',): TransferHandler
    }

    handler_class = choose_handler(keyword, location_needed_handlers)
    if handler_class and not user.location_id:
        return True

    if not handler_class:
        handler_class = choose_handler(keyword, handlers)

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
