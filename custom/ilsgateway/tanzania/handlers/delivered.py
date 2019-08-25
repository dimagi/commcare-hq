from datetime import datetime
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.exceptions import InvalidProductCodeException
from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.handlers.soh import parse_report
from custom.ilsgateway.tanzania.reminders import DELIVERY_CONFIRM_DISTRICT, DELIVERY_PARTIAL_CONFIRM, \
    DELIVERY_CONFIRM_CHILDREN, DELIVERED_CONFIRM, INVALID_PRODUCT_CODE
from custom.ilsgateway.utils import send_translated_message
import six


class DeliveryFormatter(Formatter):

    def format(self, text):
        split_text = text.split(' ', 1)
        keyword = split_text[0].lower()
        content = ' '.join('{} {}'.format(code, amount) for code, amount in parse_report(split_text[1]))
        if keyword in ['delivered', 'dlvd', 'nimepokea']:
            text = 'delivered ' + content
        return text


class DeliveredHandler(GenericStockReportHandler):

    formatter = DeliveryFormatter

    def _send_delivery_alert_to_facilities(self, location):
        locs = [c.get_id for c in location.get_children()]
        users = []
        for location_id in locs:
            users.extend(get_users_by_location_id(self.domain, location_id))

        for user in users:
            send_translated_message(user, DELIVERY_CONFIRM_CHILDREN, district_name=location.name)

    def on_success(self):
        SupplyPointStatus.objects.create(location_id=self.location_id,
                                         status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())

    def get_message(self, data):
        with localize(self.user.get_language_code()):
            products = sorted([
                (SQLProduct.objects.get(product_id=tx.product_id).code, tx.quantity)
                for tx in data['transactions']
            ], key=lambda x: x[0])
            return DELIVERED_CONFIRM % {'reply_list': ', '.join(
                ['{} {}'.format(product, quantity) for product, quantity in products]
            )}

    def on_error(self, data):
        for error in data['errors']:
            if isinstance(error, InvalidProductCodeException):
                self.respond(INVALID_PRODUCT_CODE, product_code=six.text_type(error))
                return

    def help(self):
        location = self.user.location
        if not location:
            return False
        status_type = None
        if location.location_type_name == 'FACILITY':
            status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
            self.respond(DELIVERY_PARTIAL_CONFIRM)
        elif location.location_type_name == 'DISTRICT':
            status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
            self._send_delivery_alert_to_facilities(location)
            self.respond(DELIVERY_CONFIRM_DISTRICT, contact_name=self.user.first_name + " " + self.user.last_name,
                         facility_name=location.name)
        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())
        return True
