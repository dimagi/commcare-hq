import re
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.commtrack.util import get_supply_point
from corehq.apps.sms.api import signal
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


def handle(sender, **kwargs):
    if 'verified_contact' in kwargs and 'domain' in kwargs and 'text' in kwargs and 'msg' in kwargs:
        verified_contact = kwargs['verified_contact']
        user = verified_contact.owner if verified_contact else None
        domain = kwargs['domain']
        text = kwargs['text']
        msg = kwargs['msg']

        if domain and not ILSGatewayConfig.for_domain(domain):
            return

        args = text.split()
        if not args:
            return
        keyword = args[0]
        args = args[1:]
        handler = None
        params = {
            'user': user,
            'domain': domain,
            'args': args,
            'msg': msg,
            'verified_contact': verified_contact
        }

        if keyword in ['soh', 'hmk']:
            handler = SOHHandler(**params)
        elif keyword in ['submitted', 'nimetuma']:
            handler = RandrHandler(**params)
        elif keyword in ['delivered', 'dlvd', 'nimepokea']:
            handler = DeliveredHandler(**params)
        elif keyword == 'sijapokea' or (keyword == 'not' and args and re.match("del", args[0])):
            handler = NotDeliveredHandler(**params)
        elif keyword == 'sijatuma' or (keyword == 'not' and args and re.match("sub", args[0])):
            handler = NotSubmittedHandler(**params)
        elif keyword in ['supervision', 'usimamizi']:
            handler = SupervisionHandler(**params)
        elif keyword in ['arrived', 'aliwasili']:
            handler = ArrivedHandler(**params)
        elif keyword in ['help', 'msaada']:
            handler = HelpHandler(**params)
        elif keyword in ['language', 'lang', 'lugha']:
            handler = LanguageHandler(**params)
        elif keyword in ['stop', 'acha', 'hapo']:
            handler = StopHandler(**params)
        elif keyword in ['yes', 'ndio', 'ndyo']:
            handler = YesHandler(**params)
        elif keyword in ['register', 'reg', 'join', 'sajili']:
            handler = RegisterHandler(**params)
        elif keyword == 'test':
            handler = MessageInitiatior(**params)

        if handler:
            if args:
                handler.handle()
            else:
                handler.help()

signal.connect(handle)
