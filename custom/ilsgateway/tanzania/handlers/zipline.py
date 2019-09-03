from corehq.apps.products.models import SQLProduct
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import INVALID_PRODUCT_CODE
from custom.zipline.api import ProductQuantity


class ParseError(Exception):
    pass


class ZiplineGenericHandler(KeywordHandler):

    help_message = None
    error_message = None

    def _check_quantities(self, quantities):
        for quantity in quantities:
            try:
                int(quantity)
            except ValueError:
                raise ParseError(self.error_message)

    def _check_product_codes(self, product_codes):
        for product_code in product_codes:
            try:
                SQLProduct.objects.get(code=product_code, domain=self.domain)
            except SQLProduct.DoesNotExist:
                raise ParseError(INVALID_PRODUCT_CODE % {'product_code': product_code})

    def parse_message(self, text):
        text_split = text.split()
        product_codes = text_split[::2]
        quantities = text_split[1::2]

        product_codes_len = len(product_codes)
        if product_codes_len == 0 or product_codes_len != len(quantities):
            raise ParseError(self.error_message)
        self._check_quantities(quantities)
        self._check_product_codes(product_codes)
        return list(zip(product_codes, quantities))

    def help(self):
        self.respond(self.help_message)
        return True

    def send_success_message(self):
        raise NotImplementedError()

    def invoke_api_function(self, quantities_list):
        raise NotImplementedError()

    def handle(self):
        content = self.msg.text.split(' ', 1)[1]
        quantities_list = []
        try:
            parsed_report = self.parse_message(content)
        except ParseError as e:
            self.respond(str(e))
            return True

        for product_code, quantity in parsed_report:
            quantities_list.append(ProductQuantity(product_code, quantity))

        self.invoke_api_function(quantities_list)
        self.send_success_message()
        return True
