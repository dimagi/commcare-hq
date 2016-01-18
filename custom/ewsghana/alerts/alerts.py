
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.alerts import COMPLETE_REPORT, \
    STOCKOUTS_MESSAGE, LOW_SUPPLY_MESSAGE, OVERSTOCKED_MESSAGE, RECEIPT_MESSAGE
from custom.ewsghana.utils import ProductsReportHelper
from django.utils.translation import ugettext as _



class SOHAlerts(object):

    def __init__(self, user, sql_location):
        self.user = user
        self.sql_location = sql_location

    def get_alerts(self, transactions):
        report_helper = ProductsReportHelper(self.sql_location, transactions)
        products_below = report_helper.low_supply()
        stockouts = report_helper.stockouts()
        overstocked = report_helper.overstocked()
        receipts = report_helper.receipts()
        missings = report_helper.missing_products()
        message = ""
        super_message = ""
        if missings:
            products_codes_str = ' '.join(sorted([missing.code for missing in missings]))
            message += " still missing %s. " % products_codes_str

        if stockouts:
            products_codes_str = ' '.join([stockout.sql_product.code for stockout in stockouts])
            products_names_str = ' '.join([stockout.sql_product.name for stockout in stockouts])
            message += " " + STOCKOUTS_MESSAGE % {'products': products_codes_str}
            super_message = _("stockouts %s; ") % products_names_str

        if products_below:
            products_codes_str = ' '.join([product.sql_product.code for product in products_below])
            products_names_str = ' '.join([product.sql_product.name for product in products_below])
            message += " " + LOW_SUPPLY_MESSAGE % {'low_supply': products_codes_str}
            super_message += _("below reorder level %s; ") % products_names_str

        if stockouts or products_below:
            reorders = [
                u'%s %s' % (code, amount)
                for (code, amount) in report_helper.reorders()
                if amount
            ]
            if reorders:
                message += " Please order %s." % ' '.join(reorders)

        if overstocked:
            if not message:
                products_codes_str = ' '.join([overstock.sql_product.code for overstock in overstocked])
                message += " " + OVERSTOCKED_MESSAGE % {'username': self.user.full_name,
                                                        'overstocked': products_codes_str}
            products_names_str = ' '.join([overstock.sql_product.name for overstock in overstocked])
            super_message += _("overstocked %s; ") % products_names_str

        if not message:
            if not receipts:
                message = COMPLETE_REPORT % self.user.full_name
            else:
                products_str = ' '.join(
                    [
                        "%s %s" % (SQLProduct.objects.get(product_id=receipt.product_id).code, receipt.quantity)
                        for receipt in receipts
                    ]
                )
                message = RECEIPT_MESSAGE % {'username': self.user.full_name, 'received': products_str}
        else:
            message = (_('Dear %s,') % self.user.full_name) + message

        if super_message:
            stripped_message = super_message.strip().strip(';')
            super_message = _('Dear %s, %s is experiencing the following problems: ') + stripped_message

        return message.rstrip(), super_message
