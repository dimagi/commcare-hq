from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase, StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts import ONGOING_NON_REPORTING, ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS,\
    REPORT_REMINDER, WEB_REMINDER, URGENT_NON_REPORTING, URGENT_STOCKOUT, COMPLETE_REPORT, INCOMPLETE_REPORT, \
    BELOW_REORDER_LEVELS, ABOVE_THRESHOLD, WITHOUT_RECEIPTS
from django.core.mail import send_mail
import settings
from corehq.apps.commtrack.models import CommtrackConfig
from custom.ewsghana.models import EWSGhanaConfig


def send_alert(transactions, sp, user, message):
    sp_ids = set()
    if sp and not transactions and user.get_verified_number():
        send_sms_to_verified_number(user.get_verified_number(), message)
        sp_ids.add(sp._id)


# Alert when facilities have not been reported continuously for 3 weeks
@periodic_task(run_every=crontab(hour=10, minute=00),
              queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_non_reporting():
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    domains = EWSGhanaConfig.get_all_enabled_domains()

    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            try:
                user_location = SQLLocation.objects.get(domain=domain, location_id=user.location._id)
            except AttributeError:
                continue
            if user_location:
                facilities = []
                if user_location.location_type == 'district':
                    facilities = user_location.get_children()
                elif user_location.location_type == 'region':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__location_id=user.location._id)
                fac = set()
                for facility in facilities:
                    sp = facility.supply_point_id
                    if sp and not StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand", report__date__gte=date).exists():
                        fac.add(str(facility.name))
                if fac and user.get_verified_number():
                    message = ONGOING_NON_REPORTING % " \n".join(fac)
                    send_sms_to_verified_number(user.get_verified_number(), message)
                    if user.email:
                        email = str(user.email)
                        send_mail('ONGOING NON REPORTING', message, 'commcarehq-noreply@dimagi.com', [email])


# Ongoing STOCKOUTS at SDP and RMS
@periodic_task(run_every=crontab(hour=10, minute=25),
              queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_stockout():
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            try:
                user_location = SQLLocation.objects.get(domain=domain, location_id=user.location._id)
            except AttributeError:
                continue

            if user_location:
                facilities = []
                if user_location.location_type == 'district':
                    facilities = user_location.get_children()
                elif user_location.location_type == 'region':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__location_id=user.location._id)

                fac = set()
                for facility in facilities:
                    sp = facility.supply_point_id
                    if sp and StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand", stock_on_hand=0, report__date__gte=date).exists():
                        fac.add(str(facility.name))
                if fac and user.get_verified_number():
                    if user_location.location_type == 'district':
                        message = ONGOING_STOCKOUT_AT_SDP % " \n".join(fac)
                        send_sms_to_verified_number(user.get_verified_number(), message)
                        if user.email:
                            email = str(user.email)
                            send_mail('ONGOING STOCKOUT AT SDP', message, 'commcarehq-noreply@dimagi.com', [email])
                    elif user_location.location_type == 'region':
                        message = ONGOING_STOCKOUT_AT_RMS % " \n".join(fac)
                        send_sms_to_verified_number(user.get_verified_number(), message)
                        if user.email:
                            email = str(user.email)
                            send_mail('ONGOING STOCKOUT AT RMS', message, 'commcarehq-noreply@dimagi.com', [email])


# Urgent Non-Reporting
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_non_reporting():
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            try:
                user_location = SQLLocation.objects.get(domain=domain, location_id=user.location._id)
            except AttributeError:
                continue
            if user_location:
                facilities = []
                if user_location.location_type == 'district':
                    facilities = user_location.get_children()
                elif user_location.location_type == 'region':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__location_id=user.location._id)
                elif user_location.location_type == 'country':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__parent__location_id=user.location._id)
                fac = set()
                no_rep = 0
                for facility in facilities:
                    sp = facility.supply_point_id
                    if sp and not StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand", report__date__gte=date).exists():
                        fac.add(str(facility.name))
                        no_rep += 1
                if fac and no_rep >= len(facilities) / 2 and user.get_verified_number():
                    message = URGENT_NON_REPORTING % user.location.name
                    send_sms_to_verified_number(user.get_verified_number(), message)
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT NON REPORTING', message, 'commcarehq-noreply@dimagi.com', [email])


# Urgent Stockout
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_stockout():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            try:
                user_location = SQLLocation.objects.get(domain=domain, location_id=user.location._id)
            except AttributeError:
                continue
            if user_location:
                facilities = []
                if user_location.location_type == 'district':
                    facilities = user_location.get_children()
                elif user_location.location_type == 'region':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__location_id=user.location._id)
                elif user_location.location_type == 'country':
                    facilities = SQLLocation.objects.filter(domain=domain,
                                                            parent__parent__parent__location_id=user.location._id)
                stocked_out_products = set()
                fac = set()
                no_rep = 0
                for facility in facilities:
                    sp = facility.supply_point_id
                    if sp:
                        stocked_out = StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand", stock_on_hand=0)
                        if stocked_out.exists():
                            no_rep += 1
                            fac.add(str(facility))
                            for product in stocked_out:
                                stocked_out_products.add(
                                    SQLProduct.objects.get(product_id=product.product_id).name)

                if fac and no_rep >= len(facilities) / 2 and user.get_verified_number():
                    message = URGENT_STOCKOUT % (user_location.name, ", ".join(sorted(
                        [str(product) for product in stocked_out_products])))
                    send_sms_to_verified_number(user.get_verified_number(), message)
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT STOCKOUT', message, 'commcarehq-noreply@dimagi.com', [email])


# Web reminder, once every 3 months
@periodic_task(run_every=crontab(day_of_month=1, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            if user.location and user.last_login < datetime.datetime.now() - datetime.timedelta(weeks=13) and\
                    user.get_verified_number() and \
                    (user.location.location_type == 'district' or user.location.location_type == 'region'
                     or user.location.location_type == 'country'):
                    message = WEB_REMINDER % user.name
                    send_sms_to_verified_number(user.get_verified_number(), message)
                    if user.email:
                        email = str(user.email)
                        send_mail('REMINDER TO VISIT WEBSITE', message, 'commcarehq-noreply@dimagi.com', [email])


# One week reminder when facility does not report to EWS
@periodic_task(run_every=crontab(day_of_week=1, hour=11, minute=11),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def report_reminder():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=7)
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            if user.location:
                sp = SupplyPointCase.get_by_location(user.location)
                if sp and not StockTransaction.objects.filter(
                    case_id=sp._id, type="stockonhand", report__date__gte=date).exists()\
                        and user.get_verified_number():
                    sp_ids.add(sp._id)
                    message = REPORT_REMINDER % (user.name, user.location.name)
                    send_sms_to_verified_number(user.get_verified_number(), message)
                    if user.email:
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
        send_sms_to_verified_number(user.get_verified_number(), message)
    elif missing_products:
        message = INCOMPLETE_REPORT % (user.name, user.location.name, ", ".join(sorted(missing_products)))
        send_sms_to_verified_number(user.get_verified_number(), message)


# sends overstock, understock, or SOH without receipts alerts
def stock_alerts(transactions, user):
    products_without_receipts = set()
    products_above = set()
    products_below = set()
    sp = SupplyPointCase.get_by_location(user.location)
    for i in range(0, len(transactions), 2):
        if StockState.objects.filter(case_id=sp._id, product_id=transactions[i + 1].product_id).exists():
            receipt = int(transactions[i].quantity)
            stock = int(transactions[i + 1].quantity)
            product = SQLProduct.objects.get(product_id=transactions[i].product_id).name
            last_stock = StockState.objects.get(
                case_id=sp._id, product_id=transactions[i].product_id).stock_on_hand

            stock_levels_config = CommtrackConfig.for_domain(user.domain).stock_levels_config
            over_stock_threshold = stock_levels_config.overstock_threshold
            under_stock_threshold = stock_levels_config.understock_threshold

            if stock > over_stock_threshold:
                products_above.add(product)
            elif stock < under_stock_threshold:
                products_below.add(product)
            if stock > last_stock and receipt == 0:
                products_without_receipts.add(product)

    if products_below:
        message = BELOW_REORDER_LEVELS % (user.name, user.location,
                                          ", ".join(sorted([str(prod) for prod in products_below])))
        send_sms_to_verified_number(user.get_verified_number(), message)
    elif products_above:
        message = ABOVE_THRESHOLD % (
            user.name, ", ".join(sorted([str(prod) for prod in products_above])))
        send_sms_to_verified_number(user.get_verified_number(), message)
    elif products_without_receipts:
        message = WITHOUT_RECEIPTS % (
            ', '.join(sorted([str(prod) for prod in products_without_receipts])))
        send_sms_to_verified_number(user.get_verified_number(), message)
    else:
        return False
