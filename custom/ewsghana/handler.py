import re
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ewsghana.handlers import INVALID_MESSAGE
from custom.ewsghana.handlers.receipts import ReceiptsHandler
from custom.ewsghana.handlers.requisition import RequisitionHandler
from custom.ewsghana.handlers.alerts import AlertsHandler
from custom.ewsghana.handlers.undo import UndoHandler
from custom.ewsghana.models import EWSGhanaConfig
from custom.ilsgateway.tanzania.handlers.language import LanguageHandler
from custom.ilsgateway.tanzania.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.tanzania.handlers.notsubmitted import NotSubmittedHandler


def handle(verified_contact, text, msg=None):
    user = verified_contact.owner if verified_contact else None
    domain = user.domain
    if not domain:
        return False

    if not EWSGhanaConfig.for_domain(domain):
        return False

    args = text.split()
    if not args:
        send_sms_to_verified_number(verified_contact, unicode(INVALID_MESSAGE))
        return True
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
        ('yes', 'no', 'y', 'n'): RequisitionHandler,
        # For now there is no easy way to fetch last report sent by user
        # ('undo', 'replace', 'revoke'): UndoHandler,
        ('soh',): AlertsHandler,
        ('not',): not_function(args[0]) if args else None,
        ('rec', 'receipts', 'received'): ReceiptsHandler
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
            handler.help()
            return True
    else:
        return AlertsHandler(**params).handle()
