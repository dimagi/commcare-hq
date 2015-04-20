from datetime import datetime
from corehq import Domain
from corehq.apps.commtrack.exceptions import NotAUserClassError
from corehq.apps.commtrack.sms import StockReportParser, process
from corehq.apps.sms.api import send_sms_to_verified_number

from custom.ilsgateway.tanzania.handlers import get_location
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE, SOH_THANK_YOU
import settings


class SOHHandler(KeywordHandler):

    def handle(self):
        location = get_location(self.domain, self.user, self.args[0])
        domain = Domain.get_by_name(self.domain)
        if location['location'].location_type == 'FACILITY':
            splitted_text = self.msg.text.split()
            if splitted_text[0].lower() == 'hmk':
                text = 'soh ' + ' '.join(self.msg.text.split()[1:])
            else:
                text = self.msg.text
            try:
                data = StockReportParser(domain, self.verified_contact).parse(text)
                if not data:
                    return True
                process(domain.name, data)
                SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                                 status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                                 status_value=SupplyPointStatusValues.SUBMITTED,
                                                 status_date=datetime.utcnow())
                self.respond(SOH_THANK_YOU)
            except NotAUserClassError:
                return True
            except Exception, e:  # todo: should we only trap SMSErrors?
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
                send_sms_to_verified_number(self.verified_contact, 'problem with stock report: %s' % str(e))
                return True

        return True

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
