from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase, StockState
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts import ONGOING_NON_REPORTING, ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS, \
    REPORT_REMINDER, WEB_REMINDER, URGENT_NON_REPORTING, URGENT_STOCKOUT, COMPLETE_REPORT, INCOMPLETE_REPORT, \
    STOCKOUTS_MESSAGE, LOW_SUPPLY_MESSAGE, OVERSTOCKED_MESSAGE, RECEIPT_MESSAGE
from django.core.mail import send_mail
from custom.ewsghana.utils import ProductsReportHelper
from custom.ewsghana.utils import send_test_message, can_receive_email
import settings
from custom.ewsghana.models import EWSGhanaConfig
from django.utils.translation import ugettext as _


def send_alert(transactions, sp, user, message):
    sp_ids = set()
    if sp and not transactions and user.get_verified_number():
        send_sms_to_verified_number(user.get_verified_number(), message)
        sp_ids.add(sp._id)


# Alert when facilities have not been reported continuously for 3 weeks
@periodic_task(run_every=crontab(hour=10, minute=00),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            on_going_process_user(user)


def on_going_process_user(user, test=False):
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    user_location = user.sql_location
    if not user_location:
        return

    facilities = []
    if user_location.location_type.name == 'district':
        facilities = user_location.get_children()
    elif user_location.location_type.name == 'region':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__location_id=user.location._id)
    fac = set()
    for facility in facilities:
        sp = facility.supply_point_id
        if not sp:
            continue
        transactions_exist = StockTransaction.objects.filter(
            case_id=sp,
            type="stockonhand",
            report__date__gte=date
        ).exists()
        if not transactions_exist:
            fac.add(unicode(facility.name))
    verified_number = user.get_verified_number()
    if fac and verified_number:
        message = ONGOING_NON_REPORTING % " \n".join(fac)
        if not test:
            send_sms_to_verified_number(verified_number, message)
        else:
            send_test_message(verified_number, message)
        if can_receive_email(user, verified_number):
            email = str(user.email)
            send_mail('ONGOING NON REPORTING', message, 'commcarehq-noreply@dimagi.com', [email])


# Ongoing STOCKOUTS at SDP and RMS
@periodic_task(run_every=crontab(hour=10, minute=25),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            on_going_stockout_process_user(user)


def on_going_stockout_process_user(user, test=False):
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    user_location = user.sql_location
    if not user_location:
        return

    facilities = []
    if user_location.location_type.name == 'district':
        facilities = user_location.get_children()
    elif user_location.location_type.name == 'region':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__location_id=user.location._id)

    fac = set()
    for facility in facilities:
        sp = facility.supply_point_id
        if not sp:
            continue
        stockouts = StockTransaction.objects.filter(
            case_id=sp,
            type="stockonhand",
            report__date__gte=date
        )
        if stockouts.exists() and not stockouts.exclude(stock_on_hand=0).exists():
            fac.add(unicode(facility.name))

    if fac and user.get_verified_number():
        if user_location.location_type.name == 'district':
            message = ONGOING_STOCKOUT_AT_SDP % " \n".join(fac)
            verified_number = user.get_verified_number()
            send_sms_to_verified_number(verified_number, message)
            if can_receive_email(user, verified_number):
                email = str(user.email)
                send_mail('ONGOING STOCKOUT AT SDP', message, 'commcarehq-noreply@dimagi.com', [email])
        elif user_location.location_type.name == 'region':
            message = ONGOING_STOCKOUT_AT_RMS % " \n".join(fac)
            verified_number = user.get_verified_number()
            if not test:
                send_sms_to_verified_number(verified_number, message)
            else:
                send_test_message(verified_number, message)
            if can_receive_email(user, verified_number):
                email = str(user.email)
                send_mail('ONGOING STOCKOUT AT RMS', message, 'commcarehq-noreply@dimagi.com', [email])


# Urgent Non-Reporting
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_non_reporting():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            urgent_non_reporting_process_user(user)


def urgent_non_reporting_process_user(user, test=False):
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=30)
    user_location = user.sql_location
    if not user_location:
        return
    facilities = []
    if user_location.location_type.name == 'district':
        facilities = user_location.get_children()
    elif user_location.location_type.name == 'region':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__location_id=user.location._id)
    elif user_location.location_type.name == 'country':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__parent__location_id=user.location._id)
    fac = set()
    no_rep = 0
    for facility in facilities:
        sp = facility.supply_point_id
        transaction_exists = StockTransaction.objects.filter(
            case_id=sp,
            type="stockonhand",
            report__date__gte=date
        ).exists()
        if sp and not transaction_exists:
            fac.add(unicode(facility.name))
            no_rep += 1
    if fac and no_rep >= len(facilities) / 2 and user.get_verified_number():
        message = URGENT_NON_REPORTING % user.location.name
        verified_number = user.get_verified_number()
        if not test:
            send_sms_to_verified_number(verified_number, message)
        else:
            send_test_message(verified_number, message)
        if can_receive_email(user, verified_number):
            email = str(user.email)
            send_mail('URGENT NON REPORTING', message, 'commcarehq-noreply@dimagi.com', [email])


# Urgent Stockout
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            urgent_stockout_process_user(user)


def urgent_stockout_process_user(user, test=False):
    user_location = user.sql_location
    if not user_location:
        return

    facilities = []
    if user_location.location_type.name == 'district':
        facilities = user_location.get_children()
    elif user_location.location_type.name == 'region':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__location_id=user.location._id)
    elif user_location.location_type.name == 'country':
        facilities = SQLLocation.objects.filter(domain=user.domain,
                                                parent__parent__parent__location_id=user.location._id)
    stocked_out_products = set()
    fac = set()
    no_rep = 0
    for facility in facilities:
        sp = facility.supply_point_id
        if sp:
            stocked_out = StockState.objects.filter(
                case_id=sp, section_id="stockonhand", stock_on_hand=0
            )
            if stocked_out.exists():
                no_rep += 1
                fac.add(unicode(facility))
                for product in stocked_out:
                    sql_product = SQLProduct.objects.get(product_id=product.product_id)
                    stocked_out_products.add(sql_product.name)

    if fac and no_rep >= (len(facilities) / 2) and user.get_verified_number():
        stockout_str = ", ".join(sorted(
            [unicode(product) for product in stocked_out_products]
        ))
        message = URGENT_STOCKOUT % (user_location.name, stockout_str)
        verified_number = user.get_verified_number()
        if not test:
            send_sms_to_verified_number(verified_number, message)
        else:
            send_test_message(verified_number, message)

        if can_receive_email(user, verified_number):
            email = str(user.email)
            send_mail('URGENT STOCKOUT', message, 'commcarehq-noreply@dimagi.com', [email])


# Web reminder, once every 3 months
@periodic_task(run_every=crontab(day_of_month=1, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            thirteen_days_ago = datetime.datetime.utcnow() - datetime.timedelta(weeks=13)
            if user.location and user.last_login < thirteen_days_ago and user.get_verified_number()\
                    and user.location.location_type.name in ['district', 'region', 'country']:
                    message = WEB_REMINDER % user.name
                    verified_number = user.get_verified_number()
                    send_sms_to_verified_number(verified_number, message)
                    if can_receive_email(user, verified_number):
                        email = str(user.email)
                        send_mail('REMINDER TO VISIT WEBSITE', message, 'commcarehq-noreply@dimagi.com', [email])


# One week reminder when facility does not report to EWS
@periodic_task(run_every=crontab(day_of_week=1, hour=11, minute=11),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def report_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            report_reminder_process_user(user)


def report_reminder_process_user(user, test=False):
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=7)

    if not user.location or user.location.location_type.administrative:
        return
    sp = SupplyPointCase.get_by_location(user.location)
    if not sp:
        return
    transaction_exists = StockTransaction.objects.filter(
        case_id=sp._id,
        type="stockonhand",
        report__date__gte=date
    ).exists()
    if sp and not transaction_exists and user.get_verified_number():
        message = REPORT_REMINDER % (user.name, user.location.name)
        verified_number = user.get_verified_number()
        if not test:
            send_sms_to_verified_number(verified_number, message)
        else:
            send_test_message(verified_number, message)

        if can_receive_email(user, verified_number):
            email = str(user.email)
            send_mail('REPORT REMINDER', message, 'commcarehq-noreply@dimagi.com', [email])


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
    users = get_users_by_location_id(user.location.get_id)
    in_charge_users = [
        u
        for u in users
        if u.get_verified_number() and "In Charge" in u.user_data.get('role', [])
    ]
    for in_charge_user in in_charge_users:
        send_sms_to_verified_number(in_charge_user.get_verified_number(),
                                    message % (in_charge_user.full_name, in_charge_user.location.name))
