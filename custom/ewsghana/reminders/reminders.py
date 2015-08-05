from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase, StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.reminders import STOCK_ON_HAND_REMINDER, SECOND_STOCK_ON_HAND_REMINDER, \
    SECOND_INCOMPLETE_SOH_REMINDER, THIRD_STOCK_ON_HAND_REMINDER, INCOMPLETE_SOH_TO_SUPER, STOCKOUT_REPORT, \
    RRIRV_REMINDER, WEB_REMINDER
from custom.ewsghana.utils import send_test_message
import settings

IN_CHARGE_ROLE = 'In Charge'
DAYS_UNTIL_LATE = 5


def reporting_types(domain):
    return [
        loc_type.name
        for loc_type in Domain.get_by_name(domain).location_types
        if not loc_type.administrative
    ]


def user_has_reporting_location(user):
    if not user.location:
        return False
    return user.location.location_type in reporting_types(user.domain)


def user_has_role(user, role):
    return role in user.user_data.get('role', [])


@periodic_task(run_every=crontab(day_of_week=3, hour=13, minute=58),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def first_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            roles = user.user_data.get('role')
            if roles and IN_CHARGE_ROLE in roles:
                first_soh_process_user(user)


def first_soh_process_user(user, test=False):
    if user_has_reporting_location(user):
        if user.get_verified_number():
            message = STOCK_ON_HAND_REMINDER % {'name': user.name}
            if not test:
                send_sms_to_verified_number(
                    user.get_verified_number(),
                    message
                )
            else:
                send_test_message(
                    user.get_verified_number(),
                    message
                )


@periodic_task(run_every=crontab(day_of_week=0, hour=13, minute=57),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def second_soh_reminder():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            roles = user.user_data.get('role')
            if roles and IN_CHARGE_ROLE in roles:
                second_soh_process_user(user)


def second_soh_process_user(user, test=False):
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=DAYS_UNTIL_LATE)
    supply_point = SupplyPointCase.get_by_location(user.location)
    if not supply_point:
        return

    stock_states = StockState.objects.filter(
        case_id=supply_point._id,
        last_modified_date__gte=date
    )
    products = user.sql_location.products
    location_products_ids = [product.product_id for product in products]
    reported_products_ids = [stock_state.product_id for stock_state in stock_states]
    missing_products_ids = set(location_products_ids) - set(reported_products_ids)
    if not user_has_reporting_location(user) or not user.get_verified_number():
        return

    if not stock_states:
        if not test:
            send_sms_to_verified_number(
                user.get_verified_number(),
                SECOND_STOCK_ON_HAND_REMINDER % {'name': user.name}
            )
        else:
            send_test_message(
                user.get_verified_number(),
                SECOND_STOCK_ON_HAND_REMINDER % {'name': user.name}
            )
    elif missing_products_ids:
        products_names = [
            product.name
            for product in products
            if product.product_id in missing_products_ids
        ]
        if not test:
            send_sms_to_verified_number(
                user.get_verified_number(),
                SECOND_INCOMPLETE_SOH_REMINDER %
                {'name': user.name, 'products': ", ".join(products_names)}
            )
        else:
            send_test_message(
                user.get_verified_number(),
                SECOND_INCOMPLETE_SOH_REMINDER %
                {'name': user.name, 'products': ", ".join(products_names)}
            )


@periodic_task(run_every=crontab(day_of_week=2, hour=13, minute=54),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def third_soh_to_super():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        facilities = SQLLocation.objects.filter(location_type__name__in=reporting_types(domain))
        users = CommCareUser.by_domain(domain)
        third_soh_process_users_and_facilities(users, facilities)


def third_soh_process_users_and_facilities(users, facilities, test=False):
    date = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_UNTIL_LATE)
    for facility in facilities:
        if not facility.supply_point_id:
            continue
        on_time_products = StockState.objects.filter(
            case_id=facility.supply_point_id,
            last_modified_date__gte=date
        )

        location_products = [product.product_id for product in facility.products]
        reported_products = [stock_state.product_id for stock_state in on_time_products]
        missing_products = set(location_products) - set(reported_products)
        if not on_time_products:
            for user in users:
                if user.location and user.location._id == facility.location_id \
                        and user_has_role(user, IN_CHARGE_ROLE) and user.get_verified_number():
                    if not test:
                        send_sms_to_verified_number(
                            user.get_verified_number(),
                            THIRD_STOCK_ON_HAND_REMINDER % {'name': user.name, 'facility': facility.name}
                        )
                    else:
                        send_test_message(
                            user.get_verified_number(),
                            THIRD_STOCK_ON_HAND_REMINDER % {'name': user.name, 'facility': facility.name}
                        )
        elif missing_products:
            for user in users:
                if user.location and user.location._id == facility.location_id and \
                        user_has_role(user, IN_CHARGE_ROLE) and user.get_verified_number():
                    if not test:
                        send_sms_to_verified_number(
                            user.get_verified_number(),
                            INCOMPLETE_SOH_TO_SUPER % {
                                'name': user.name,
                                'facility': facility.name,
                                'products': ", ".join([SQLProduct.objects.get(
                                    product_id=product_id).name for product_id in missing_products])
                            }
                        )
                    else:
                        send_test_message(
                            user.get_verified_number(),
                            INCOMPLETE_SOH_TO_SUPER % {
                                'name': user.name,
                                'facility': facility.name,
                                'products': ", ".join([SQLProduct.objects.get(
                                    product_id=product_id).name for product_id in missing_products])
                            }
                        )


@periodic_task(run_every=crontab(day_of_month="2", hour=14, minute=6),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def stockout_notification_to_web_supers():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            stockout_process_user(user)


def stockout_process_user(user, test=False):
    if user_has_reporting_location(user):
        location = user.location
        supply_point = SupplyPointCase.get_by_location(location)
        if supply_point and user.get_verified_number():
            products = [
                SQLProduct.objects.get(product_id=state.product_id).name
                for state in StockState.objects.filter(
                    case_id=supply_point._id, stock_on_hand=0,
                    product_id__in=[product.product_id for product in location.sql_location.products]
                )
            ]
            if products:
                if not test:
                    send_sms_to_verified_number(
                        user.get_verified_number(),
                        STOCKOUT_REPORT % {
                            'name': user.name,
                            'facility': supply_point.name,
                            'date': datetime.datetime.utcnow().strftime('%b %d'),
                            'products': ", ".join(products)
                        }
                    )
                else:
                    send_test_message(
                        user.get_verified_number(),
                        STOCKOUT_REPORT % {
                            'name': user.name,
                            'facility': supply_point.name,
                            'date': datetime.datetime.utcnow().strftime('%b %d'),
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


def rrirv_process_user(user, test=False):
    if user_has_reporting_location(user) and user_has_role(user, IN_CHARGE_ROLE):
        if user.get_verified_number():
            if not test:
                send_sms_to_verified_number(user.get_verified_number(), RRIRV_REMINDER % {'name': user.name})
            else:
                send_test_message(user.get_verified_number(), RRIRV_REMINDER % {'name': user.name})


@periodic_task(run_every=crontab(month_of_year='1,4,7,10', day_of_month=4, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    domains = EWSGhanaConfig.get_all_enabled_domains()
    for domain in domains:
        for user in CommCareUser.by_domain(domain):
            visit_website_process_user(user)


def visit_website_process_user(user, test=False):
    date = datetime.datetime.utcnow() - datetime.timedelta(weeks=13)
    if user.last_login < date and user.get_verified_number():
        if not test:
            send_sms_to_verified_number(user.get_verified_number(), WEB_REMINDER % {'name': user.name})
        else:
            send_test_message(user.get_verified_number(), WEB_REMINDER % {'name': user.name})
