from __future__ import absolute_import
from datetime import datetime
from casexml.apps.stock.const import TRANSACTION_TYPE_LA, SECTION_TYPE_STOCK
from casexml.apps.stock.models import StockTransaction, StockReport
from django.db import transaction

from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import SQLProduct
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.handlers.soh import parse_report
from custom.ilsgateway.tanzania.reminders import LOSS_ADJUST_HELP, LOSS_ADJUST_BAD_FORMAT, LOSS_ADJUST_CONFIRM, \
    LOSS_ADJUST_NO_SOH


class LossAndAdjustment(KeywordHandler):

    def _create_stock_transaction(self, report, product_id, quantity):
        current_soh = StockState.objects.get(product_id=product_id, case_id=self.case_id).stock_on_hand
        StockTransaction.objects.create(
            report=report,
            section_id=SECTION_TYPE_STOCK,
            type=TRANSACTION_TYPE_LA,
            case_id=self.case_id,
            product_id=product_id,
            quantity=quantity,
            stock_on_hand=current_soh + quantity
        )

    def handle(self):
        keyword, content = self.msg.text.split(' ', 1)

        parsed_report = parse_report(content.replace('+', ''))
        if not parsed_report:
            self.respond(LOSS_ADJUST_BAD_FORMAT)
            return True

        now = datetime.utcnow()
        error = False
        products_without_soh = set()
        with transaction.atomic():
            report = StockReport.objects.create(
                form_id='ilsgateway-xform',
                date=now,
                server_date=now,
                type='balance',
                domain=self.domain
            )
            for product_code, quantity in parsed_report:
                try:
                    product_id = SQLProduct.objects.get(
                        domain=self.domain,
                        code__iexact=product_code
                    ).product_id
                    self._create_stock_transaction(report, product_id, quantity)
                except SQLProduct.DoesNotExist:
                    error = True
                except StockState.DoesNotExist:
                    products_without_soh.add(product_code.lower())
        if error:
            self.respond(LOSS_ADJUST_BAD_FORMAT)
        elif products_without_soh:
            self.respond(LOSS_ADJUST_NO_SOH, products_list=', '.join(sorted(products_without_soh)))
        else:
            self.respond(LOSS_ADJUST_CONFIRM)
        return True

    def help(self):
        self.respond(LOSS_ADJUST_HELP)
        return True
