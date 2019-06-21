from __future__ import absolute_import
from __future__ import unicode_literals
import re
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.toggles import EMG_AND_REC_SMS_HANDLERS
from corehq.util.translation import localize
from custom.ilsgateway.slab.handlers.transfer import TransferHandler

from custom.ilsgateway.tanzania.handlers.delivered import DeliveredHandler
from custom.ilsgateway.tanzania.handlers.emg import EmergencyHandler
from custom.ilsgateway.tanzania.handlers.help import HelpHandler
from custom.ilsgateway.tanzania.handlers.la import LossAndAdjustment
from custom.ilsgateway.tanzania.handlers.language import LanguageHandler
from custom.ilsgateway.tanzania.handlers.messageinitiator import MessageInitiatior
from custom.ilsgateway.tanzania.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.tanzania.handlers.notsubmitted import NotSubmittedHandler
from custom.ilsgateway.tanzania.handlers.rec import ReceiptHandler
from custom.ilsgateway.tanzania.handlers.register import RegisterHandler
from custom.ilsgateway.tanzania.handlers.soh import SOHHandler
from custom.ilsgateway.tanzania.handlers.stockout import StockoutHandler
from custom.ilsgateway.tanzania.handlers.stop import StopHandler
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.reminders import CONTACT_SUPERVISOR
import six


def choose_handler(keyword, handlers):
    for k, v in six.iteritems(handlers):
        if keyword.lower() in k:
            return v
    return None


def handle(verified_contact, text, msg):
    if verified_contact:
        user = verified_contact.owner
        domain = verified_contact.domain
    elif msg.domain:
        user = None
        domain = msg.domain
    else:
        return False

    if not ILSGatewayConfig.for_domain(domain):
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

    handlers_for_unregistered_or_registered_users = {
        ('register', 'reg', 'join', 'sajili'): RegisterHandler,
    }

    handlers_for_registered_users = {
        ('help', 'msaada'): HelpHandler,
        ('language', 'lang', 'lugha'): LanguageHandler,
        ('stop', 'acha', 'hapo'): StopHandler,
        ('test',): MessageInitiatior,
    }

    handlers_for_registered_users_with_location = {
        ('soh', 'hmk'): SOHHandler,
        ('delivered', 'dlvd', 'nimepokea'): DeliveredHandler,
        ('sijapokea',): NotDeliveredHandler,
        ('sijatuma',): NotSubmittedHandler,
        ('la', 'um'): LossAndAdjustment,
        ('stockout', 'hakuna'): StockoutHandler,
        ('not',): not_function(args[0]) if args else None,
        ('trans',): TransferHandler
    }

    if EMG_AND_REC_SMS_HANDLERS.enabled(domain):
        handlers_for_registered_users_with_location[('emg',)] = EmergencyHandler
        handlers_for_registered_users_with_location[('rec',)] = ReceiptHandler

    handler_class = (
        choose_handler(keyword, handlers_for_unregistered_or_registered_users) or
        choose_handler(keyword, handlers_for_registered_users) or
        choose_handler(keyword, handlers_for_registered_users_with_location)
    )

    if (
        not user and
        handler_class not in list(handlers_for_unregistered_or_registered_users.values())
    ):
        return True

    if (
        handler_class in list(handlers_for_registered_users_with_location.values()) and
        (not user or not user.location_id)
    ):
        return True

    handler = handler_class(**params) if handler_class else None
    if handler:
        if args:
            return handler.handle()
        else:
            return handler.help()
    elif keyword != 'l':
        with localize(verified_contact.owner.get_language_code()):
            send_sms_to_verified_number(verified_contact, six.text_type(CONTACT_SUPERVISOR))
        return True
