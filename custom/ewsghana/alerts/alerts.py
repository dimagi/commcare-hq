from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ewsghana.alerts import COMPLETE_REPORT, INCOMPLETE_REPORT, \
    STOCKOUTS_MESSAGE, LOW_SUPPLY_MESSAGE, OVERSTOCKED_MESSAGE, RECEIPT_MESSAGE
from custom.ewsghana.alerts.ongoing_non_reporting import OnGoingNonReporting
from custom.ewsghana.alerts.ongoing_stockouts import OnGoingStockouts
from custom.ewsghana.alerts.urgent_alerts import UrgentNonReporting, UrgentStockoutAlert
from custom.ewsghana.utils import ProductsReportHelper
import settings
from custom.ewsghana.models import EWSGhanaConfig
from django.utils.translation import ugettext as _


# Alert when facilities have not been reported continuously for 3 weeks
@periodic_task(run_every=crontab(hour=10, minute=00),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        OnGoingNonReporting(domain).send()


# Ongoing STOCKOUTS at SDP and RMS
@periodic_task(run_every=crontab(hour=10, minute=25),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        OnGoingStockouts(domain).send()
        OnGoingNonReporting(domain).send()


# Urgent Non-Reporting
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        UrgentNonReporting(domain)


# Urgent Stockout
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        UrgentStockoutAlert(domain)


# Checking if report was complete or not
def report_completion_check(user):
    sp_id = SQLLocation.objects.get(domain=user.domain, location_id=user.location._id).supply_point_id
    now = datetime.datetime.utcnow()
    reported_products = set(StockTransaction.objects.filter(case_id=sp_id, type='stockonhand',
                                                            report__date=now).values_list('sql_product__name',
                                                                                          flat=True))
    expected_products = set(SQLProduct.objects.filter(domain=user.domain).values_list('name', flat=True))
    missing_products = set.difference(reported_products, expected_products)

    if not missing_products:
        message = COMPLETE_REPORT
        send_sms_to_verified_number(user.get_verified_number(), message % user.username)
    elif missing_products:
        message = INCOMPLETE_REPORT % (user.name, user.location.name, ", ".join(sorted(missing_products)))
        send_sms_to_verified_number(user.get_verified_number(), message)


# sends overstock, understock, or SOH without receipts alerts
def stock_alerts(transactions, user):
    report_helper = ProductsReportHelper(user.sql_location, transactions)
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
        send_message_to_admins(user, super_message.rstrip())
    send_sms_to_verified_number(user.get_verified_number(), message.rstrip())


def send_message_to_admins(user, message):
    users = get_users_by_location_id(user.domain, user.location.get_id)
    in_charge_users = [
        u
        for u in users
        if u.get_verified_number() and "In Charge" in u.user_data.get('role', [])
    ]
    for in_charge_user in in_charge_users:
        send_sms_to_verified_number(in_charge_user.get_verified_number(),
                                    message % (in_charge_user.full_name, in_charge_user.location.name))
