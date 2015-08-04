from datetime import datetime
from django.conf import settings
from corehq.apps.commtrack.exceptions import NotAUserClassError
from corehq.apps.commtrack.sms import StockReportParser, process
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.api import send_sms_to_verified_number

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE, SOH_THANK_YOU


class SOHHandler(KeywordHandler):

    def handle(self):
        location = self.user.location
        domain = Domain.get_by_name(self.domain)

        if not location:
            try:
                location_id = SQLLocation.objects.get(domain=self.domain, site_code=self.args[0]).location_id
            except SQLLocation.DoesNotExist:
                return False
        else:
            location_id = location.get_id
        if location.location_type == 'FACILITY':
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
                SupplyPointStatus.objects.create(location_id=location_id,
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

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
