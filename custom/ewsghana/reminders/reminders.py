from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders import STOCK_ON_HAND_REMINDER, SECOND_STOCK_ON_HAND_REMINDER, \
    SECOND_INCOMPLETE_SOH_REMINDER, THIRD_STOCK_ON_HAND_REMINDER, INCOMPLETE_SOH_TO_SUPER, STOCKOUT_REPORT, \
    RRIRV_REMINDER, WEB_REMINDER
import settings

IN_CHARGE_ROLE = 'In Charge'


def user_has_location_type(user, location_type):
    if not user.location:
        return False
    return user.location.location_type == location_type


def user_has_role(user, role):
    return user.user_data.get('role') == role


@periodic_task(run_every=crontab(day_of_week=3, hour=13, minute=58),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            first_soh_process_user(user)


def first_soh_process_user(user):
    if user_has_location_type(user, 'facility') and user_has_role(user, IN_CHARGE_ROLE):
        supply_point = SupplyPointCase.get_by_location(user.location)
        transaction_exists = StockTransaction.objects.filter(
            case_id=supply_point._id,
            type='stockonhand'
        ).exists()
        if supply_point and not transaction_exists and user.get_verified_number():
            message = STOCK_ON_HAND_REMINDER % {'name': user.name}
            send_sms_to_verified_number(
                user.get_verified_number(),
                message
            )


@periodic_task(run_every=crontab(day_of_week=0, hour=13, minute=57),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_soh_reminder():
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=5)
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            second_soh_process_user(user, date)


def second_soh_process_user(user, date):
    supply_point = SupplyPointCase.get_by_location(user.location)
    if not supply_point:
        return

    exists = StockTransaction.objects.filter(
        case_id=supply_point._id,
        type='stockonhand',
        report__date__gte=date
    ).exists()

    if user_has_location_type(user, 'facility') and user_has_role(user, IN_CHARGE_ROLE):
        if not exists and user.get_verified_number():
            send_sms_to_verified_number(
                user.get_verified_number(),
                SECOND_STOCK_ON_HAND_REMINDER % {'name': user.name}
            )
    elif not exists and user.get_verified_number():
        products = [
            SQLProduct.objects.get(product_id=transaction.product_id).name
            for transaction in StockTransaction.objects.filter(
                case_id=supply_point._id,
                type='stockout',
                report__date__gte=date
            )
        ]
        send_sms_to_verified_number(
            user.get_verified_number(),
            SECOND_INCOMPLETE_SOH_REMINDER % {'name': user.name, 'products': ", ".join(products)}
        )


@periodic_task(run_every=crontab(day_of_week=2, hour=13, minute=54),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_soh_to_super():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        facilities = Location.filter_by_type(domain, 'facility')
        users = CommCareUser.by_domain(domain)
        third_soh_process_users_and_facilities(users, facilities)


def third_soh_process_users_and_facilities(users, facilities):
    for facility in facilities:
        on_time_products = StockTransaction.objects.filter(case_id=facility._id, type='stockonhand')
        missing_products = StockTransaction.objects.filter(case_id=facility._id, type='stockedout')

        if not on_time_products:
            for user in users:
                if user.location and user.location._id == facility._id \
                        and user_has_role(user, IN_CHARGE_ROLE) and user.get_verified_number():
                    send_sms_to_verified_number(
                        user.get_verified_number(),
                        THIRD_STOCK_ON_HAND_REMINDER % {'name': user.name, 'facility': facility.name}
                    )
        elif missing_products:
            for user in users:
                if user.location and user.location._id == facility._id and \
                        user_has_role(user, IN_CHARGE_ROLE) and user.get_verified_number():
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
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            stockout_process_user(user)


def stockout_process_user(user):
    if user_has_location_type(user, 'facility'):
        supply_point = SupplyPointCase.get_by_location(user.location)
        transaction_exists = StockTransaction.objects.filter(
            case_id=supply_point._id,
            stock_on_hand=0
        ).exists()

        if supply_point and transaction_exists and user.get_verified_number():
            products = [
                SQLProduct.objects.get(product_id=transaction.product_id).name
                for transaction in StockTransaction.objects.filter(
                    case_id=supply_point._id,
                    stock_on_hand=0
                )
            ]
            send_sms_to_verified_number(
                user.get_verified_number(),
                STOCKOUT_REPORT % {
                    'name': user.name,
                    'facility': supply_point.name,
                    'date': datetime.datetime.now().strftime('%b %d'),
                    'products': ", ".join(products)
                }
            )


@periodic_task(run_every=crontab(day_of_month="28", hour=14, minute=15),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_submit_rrirv():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            rrirv_process_user(user)


def rrirv_process_user(user):
    if user_has_location_type(user, 'facility') and user_has_role(user, IN_CHARGE_ROLE):
        supply_point = SupplyPointCase.get_by_location(user.location)
        transaction_exists = StockTransaction.objects.filter(
            case_id=supply_point._id,
            type='stockonhand'
        ).exists()
        if supply_point and not transaction_exists and user.get_verified_number():
            send_sms_to_verified_number(user.get_verified_number(), RRIRV_REMINDER % {'name': user.name})


@periodic_task(run_every=crontab(month_of_year='1,4,7,10', day_of_month=4, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            visit_website_process_user(user)


def visit_website_process_user(user):
    date = datetime.datetime.now() - datetime.timedelta(weeks=13)
    if user.last_login < date and user.get_verified_number():
        send_sms_to_verified_number(user.get_verified_number(), WEB_REMINDER % {'name': user.name})
