import re
from custom.ilsgateway.handlers.arrived import ArrivedHandler
from custom.ilsgateway.handlers.delivered import DeliveredHandler
from custom.ilsgateway.handlers.help import HelpHandler
from custom.ilsgateway.handlers.language import LanguageHandler
from custom.ilsgateway.handlers.messageinitiator import MessageInitiatior
from custom.ilsgateway.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.handlers.notsubmitted import NotSubmittedHandler
from custom.ilsgateway.handlers.register import RegisterHandler
from custom.ilsgateway.handlers.soh import SOHHandler
from custom.ilsgateway.handlers.stop import StopHandler
from custom.ilsgateway.handlers.supervision import SupervisionHandler
from custom.ilsgateway.handlers.randr import RandrHandler
from custom.ilsgateway.handlers.yes import YesHandler
from custom.ilsgateway.models import ILSGatewayConfig


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
        ('register', 'reg', 'join', 'sajili'): RegisterHandler,
        ('test',): MessageInitiatior,
        ('not',): not_function(args[0]) if args else None
    }

    def choose_handler(keyword):
        for k, v in handlers.iteritems():
            if keyword in k:
                return v
        return None

    handler_class = choose_handler(keyword)
    handler = handler_class(**params) if handler_class else None

    if handler:
        if args:
            handler.handle()
        else:
            handler.help()
    return False
