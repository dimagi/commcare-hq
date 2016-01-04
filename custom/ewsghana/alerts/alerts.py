import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reminders.util import get_verified_number_for_recipient
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts import COMPLETE_REPORT, INCOMPLETE_REPORT, \
    STOCKOUTS_MESSAGE, LOW_SUPPLY_MESSAGE, OVERSTOCKED_MESSAGE, RECEIPT_MESSAGE
from custom.ewsghana.utils import ProductsReportHelper
from django.utils.translation import ugettext as _


# Checking if report was complete or not
from dimagi.utils.couch.database import iter_docs


def report_completion_check(user):
    sp_id = SQLLocation.objects.get(domain=user.domain, location_id=user.location.location_id).supply_point_id
    now = datetime.datetime.utcnow()
    reported_products = set(StockTransaction.objects.filter(case_id=sp_id, type='stockonhand',
                                                            report__date=now).values_list('sql_product__name',
                                                                                          flat=True))
    expected_products = set(SQLProduct.objects.filter(domain=user.domain).values_list('name', flat=True))
    missing_products = set.difference(reported_products, expected_products)

    if not missing_products:
        message = COMPLETE_REPORT
        send_sms_to_verified_number(get_verified_number_for_recipient(user), message % user.username)
    elif missing_products:
        message = INCOMPLETE_REPORT % (user.name, user.location.name, ", ".join(sorted(missing_products)))
        send_sms_to_verified_number(get_verified_number_for_recipient(user), message)


# sends overstock, understock, or SOH without receipts alerts
def stock_alerts(transactions, verified_number):
    user = verified_number.owner
    sql_location = user.sql_location
    report_helper = ProductsReportHelper(sql_location, transactions)
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
            message += " " + OVERSTOCKED_MESSAGE % {'username': user.full_name, 'overstocked': products_codes_str}
        products_names_str = ' '.join([overstock.sql_product.name for overstock in overstocked])
        super_message += _("overstocked %s; ") % products_names_str

    if not message:
        if not receipts:
            message = COMPLETE_REPORT % user.full_name
        else:
            products_str = ' '.join(
                [
                    "%s %s" % (SQLProduct.objects.get(product_id=receipt.product_id).code, receipt.quantity)
                    for receipt in receipts
                ]
            )
            message = RECEIPT_MESSAGE % {'username': user.full_name, 'received': products_str}
    else:
        message = (_('Dear %s,') % user.full_name) + message

    if super_message:
        stripped_message = super_message.strip().strip(';')
        super_message = _('Dear %s, %s is experiencing the following problems: ') + stripped_message
        send_message_to_admins(user, sql_location, super_message.rstrip())
    send_sms_to_verified_number(verified_number, message.rstrip())


def send_message_to_admins(user, sql_location, message):
    in_charge_users = map(CommCareUser.wrap, iter_docs(
        CommCareUser.get_db(),
        [in_charge.user_id for in_charge in user.sql_location.facilityincharge_set.all()]
    ))
    for in_charge_user in in_charge_users:
        verified_number = get_verified_number_for_recipient(in_charge_user)
        if not verified_number:
            continue
        send_sms_to_verified_number(verified_number, message % (in_charge_user.full_name, sql_location.name))
