import re
from custom.ewsghana.handlers.registration import RegistrationHandler
from custom.ewsghana.handlers.requisition import RequisitionHandler
from custom.ewsghana.handlers.undo import UndoHandler
from custom.ilsgateway.tanzania.handlers.language import LanguageHandler
from custom.ilsgateway.tanzania.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.tanzania.handlers.notsubmitted import NotSubmittedHandler


def handle(verified_contact, text, msg=None):
    user = verified_contact.owner if verified_contact else None
    domain = user.domain

    # if domain and not ILSGatewayConfig.for_domain(domain):
    #     return False

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
        ('language', 'lang', 'lugha'): LanguageHandler,
        ('reg', 'register'): RegistrationHandler,
        ('yes', 'no', 'y', 'n'): RequisitionHandler,
        ('undo', 'replace', 'revoke'): UndoHandler,
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