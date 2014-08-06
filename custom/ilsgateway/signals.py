from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.commtrack.sms import signal
from corehq.apps.commtrack.util import get_supply_point
from custom.ilsgateway.handlers.delivered import DeliveredHandler
from custom.ilsgateway.handlers.notdelivered import NotDeliveredHandler
from custom.ilsgateway.handlers.notsubmitted import NotSubmittedHandler
from custom.ilsgateway.handlers.soh import SOHHandler
from custom.ilsgateway.handlers.supervision import SupervisionHandler
from custom.ilsgateway.handlers.randr import RandrHandler


def handle(sender, **kwargs):
    if 'verified_contact' in kwargs and 'domain' in kwargs and 'text' in kwargs and 'msg' in kwargs:
        verified_contact = kwargs['verified_contact']
        user = verified_contact.owner
        domain = kwargs['domain']
        text = kwargs['text']
        msg = kwargs['msg']

        #TODO check that domain has ILS gateway enabled
        #if not ILSGatewayConfig.for_domain(domain.name)"
        #return

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
        elif keyword == 'sijapokea':
            handler = NotDeliveredHandler(**params)
        elif keyword == 'sijatuma':
            handler = NotSubmittedHandler(**params)
        elif keyword in ['supervision', 'usimamizi']:
            handler = SupervisionHandler(**params)

        if handler:
            if args:
                handler.handle()
            else:
                handler.help()

signal.connect(handle)
