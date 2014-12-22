from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.reminders import DOMAIN, STOCK_ON_HAND_REMINDER, SECOND_STOCK_ON_HAND_REMINDER, \
    SECOND_INCOMPLETE_SOH_REMINDER, THIRD_STOCK_ON_HAND_REMINDER, INCOMPLETE_SOH_TO_SUPER, STOCKOUT_REPORT, \
    RRIRV_REMINDER, WEB_REMINDER
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import update_statuses
import settings


def send_reminder(transactions, sp, user, message):
    sp_ids = set()
    if sp and not transactions and user.get_verified_number():
        send_sms_to_verified_number(user.get_verified_number(), message)
        sp_ids.add(sp._id)
    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


@periodic_task(run_every=crontab(day_of_week=3, hour=13, minute=58),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_soh_reminder():
    sp_ids = set()
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location and user.location.location_type == 'facility' \
                and user.user_data.get('role') != 'In Charge':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not StockTransaction.objects.filter(case_id=sp._id, type='stockonhand').exists() \
                    and user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(),
                                            STOCK_ON_HAND_REMINDER % {'name': user.name})
                sp_ids.add(sp._id)
    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


@periodic_task(run_every=crontab(day_of_week=0, hour=13, minute=57),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_soh_reminder():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=5)
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location and user.location.location_type == 'facility' \
                and user.user_data.get('role') != 'In Charge':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not StockTransaction.objects.filter(
                    case_id=sp._id, type='stockonhand', report__date__gte=date).exists() \
                    and user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(),
                                            SECOND_STOCK_ON_HAND_REMINDER % {'name': user.name})
        elif sp and not StockTransaction.objects.filter(
                case_id=sp._id, type='stockout', report__date__gte=date).exists() \
                and user.get_verified_number():
                send_sms_to_verified_number(
                    user.get_verified_number(),
                    SECOND_INCOMPLETE_SOH_REMINDER % {'name': user.name, 'products': ", ".join([
                        SQLProduct.objects.get(product_id=transaction.product_id).name for transaction in
                        StockTransaction.objects.filter(case_id=sp._id, type='stockout',
                                                        report__date__gte=date)])})
                sp_ids.add(sp._id)
    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


@periodic_task(run_every=crontab(day_of_week=2, hour=13, minute=54),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_soh_to_super():
    facilities = Location.filter_by_type(DOMAIN, 'facility')
    users = CommCareUser.by_domain(DOMAIN)
    for facility in facilities:
        on_time_products = StockTransaction.objects.filter(case_id=facility._id, type='stockonhand')
        missing_products = StockTransaction.objects.filter(case_id=facility._id, type='stockedout')

        if not on_time_products:
            for user in users:
                if user.location and user.location._id == facility._id \
                        and user.user_data.get('role') == 'In Charge' and user.get_verified_number():
                    send_sms_to_verified_number(user.get_verified_number(),
                                                THIRD_STOCK_ON_HAND_REMINDER % {
                                                    'name': user.name,
                                                    'facility': facility.name})
        elif missing_products:
            for user in users:
                if user.location and user.location._id == facility._id \
                        and user.user_data.get('role') == 'In Charge'and user.get_verified_number():
                    send_sms_to_verified_number(
                        user.get_verified_number(),
                        INCOMPLETE_SOH_TO_SUPER % {
                            'name': user.name,
                            'facility': facility.name,
                            'products': ", ".join([SQLProduct.objects.get(
                                product_id=product.product_id).name for product in missing_products])})


@periodic_task(run_every=crontab(day_of_month="2", hour=14, minute=6),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def stockout_notification_to_web_supers():
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location and user.location.location_type == 'facility':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and StockTransaction.objects.filter(case_id=sp._id, type='stockout').exists() \
                    and user.get_verified_number():
                send_sms_to_verified_number(
                    user.get_verified_number(),
                    STOCKOUT_REPORT % {'name': user.name, 'facility': sp.name,
                                       'date': datetime.datetime.now().strftime('%b %d'),
                                       'products': ", ".join([SQLProduct.objects.get(
                                           product_id=transaction.product_id).name for transaction in
                                           StockTransaction.objects.filter(case_id=sp._id, type='stockout')])})


@periodic_task(run_every=crontab(day_of_month="28", hour=14, minute=15),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_submit_rrirv():
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location and user.location.location_type == 'facility' \
                and user.user_data.get('role') != 'In Charge':
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not StockTransaction.objects.filter(case_id=sp._id, type='stockonhand').exists() \
                    and user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), RRIRV_REMINDER % {'name': user.name})


@periodic_task(run_every=crontab(month_of_year='1,4,7,10', day_of_month=4, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    for user in CommCareUser.by_domain(DOMAIN):
        if user.last_login < datetime.datetime.now() - datetime.timedelta(weeks=13) and user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), WEB_REMINDER % {'name': user.name})
