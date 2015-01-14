from celery.schedules import crontab
from celery.task import periodic_task
import datetime
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase, StockState
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.alerts import ONGOING_NON_REPORTING, ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS,\
    REPORT_REMINDER, DOMAIN, WEB_REMINDER, URGENT_NON_REPORTING, URGENT_STOCKOUT, COMPLETE_REPORT, INCOMPLETE_REPORT, \
    BELOW_REORDER_LEVELS, ABOVE_THRESHOLD, WITHOUT_RECEIPTS
from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import update_statuses
from django.core.mail import send_mail
import settings


def send_alert(transactions, sp, user, message):
    sp_ids = set()
    if sp and not transactions and user.get_verified_number():
        send_sms_to_verified_number(user.get_verified_number(), message)
        sp_ids.add(sp._id)
    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.ALERT_SENT)


#Alert when facilities have not been reported continuously for 3 weeks
@periodic_task(run_every=crontab(hour=10, minute=00),
              queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_non_reporting():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    for user in CommCareUser.by_domain(DOMAIN):
        try:
            user_location = SQLLocation.objects.get(domain=DOMAIN, location_id=user.location._id)
        except:
            pass
        if user_location:
#            user_location = SQLLocation.objects.get(location_id=user.location._id)
            if user_location.location_type == 'district':
                facilities = user_location.get_children()
                fac = set()
                if facilities:
                    for facility in facilities:
                        sp = facility.supply_point_id
                        if sp and not StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand",
                            report__date__gte=date).exists() and user.get_verified_number():
                            fac.add(str(facility.name))
                            sp_ids.add(sp)
                    if fac:
                        send_sms_to_verified_number(user.get_verified_number(), ONGOING_NON_REPORTING % " \n".join(fac))
                        if user.email:
                            email = str(user.email)
                            send_mail('ONGOING NON REPORTING', ONGOING_NON_REPORTING % " \n".join(fac),
                                      'commcarehq-noreply@dimagi.com', [email])

                        update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY,
                                        SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'region':
                districts = user_location.get_children()
                for district in districts:
                    facilities = district.get_children()
                    fac = set()
                    if facilities:
                        for facility in facilities:
                            sp = facility.supply_point_id
                            if sp and not StockTransaction.objects.filter(
                                case_id=sp, type="stockonhand",
                                report__date__gte=date).exists() and user.get_verified_number():
                                fac.add(str(facility.name))
                                sp_ids.add(sp)
                    if fac:
                        send_sms_to_verified_number(user.get_verified_number(), ONGOING_NON_REPORTING % " \n".join(fac))
                        if user.email:
                            email = str(user.email)
                            send_mail('ONGOING NON REPORTING', ONGOING_NON_REPORTING % " \n".join(fac),
                                      'commcarehq-noreply@dimagi.com', [email])

                        update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY,
                                        SupplyPointStatusValues.REMINDER_SENT)


#Ongoing STOCKOUTS at SDP and RMS
@periodic_task(run_every=crontab(hour=10, minute=25),
              queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def on_going_stockout():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    for user in CommCareUser.by_domain(DOMAIN):
        try:
            user_location = SQLLocation.objects.get(domain=DOMAIN, location_id=user.location._id)
        except:
            pass
        if user_location:
            if user_location.location_type == 'district':
                facilities = user_location.get_children()
                fac = set()
                if facilities:
                    for facility in facilities:
                        sp = facility.supply_point_id
                        if sp and StockTransaction.objects.filter(
                                case_id=sp, type="stockonhand", stock_on_hand=0, report__date__gte=date).exists() and \
                                user.get_verified_number():
                            fac.add(str(facility.name))
                            sp_ids.add(sp)
                    if fac:
                        send_sms_to_verified_number(user.get_verified_number(), ONGOING_STOCKOUT_AT_SDP " \n".join(fac))
                        if user.email:
                            email = str(user.email)
                            send_mail('ONGOING STOCKOUT AT SDP', ONGOING_STOCKOUT_AT_SDP % " \n".join(fac),
                                      'commcarehq-noreply@dimagi.com', [email])

                        update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY,
                                        SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'region':
                districts = user_location.get_children()
                fac = set()
                for district in districts:
                    facilities = district.get_children()
                    if facilities:
                        for facility in facilities:
                            sp = facility.supply_point_id
                            if sp and StockTransaction.objects.filter(
                                case_id=sp, type="stockonhand", stock_on_hand=0, report__date__gte=date).exists() \
                                    and user.get_verified_number():
                                fac.add(str(facility.name))
                                sp_ids.add(sp)
                if fac:
                    send_sms_to_verified_number(user.get_verified_number(), ONGOING_STOCKOUT_AT_RMS % " \n".join(fac))
                    if user.email:
                        email = str(user.email)
                        send_mail('ONGOING STOCKOUT AT RMS', ONGOING_STOCKOUT_AT_RMS % " \n".join(fac),
                                  'commcarehq-noreply@dimagi.com', [email])

                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


#Urgent Non-Reporting
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_non_reporting():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    for user in CommCareUser.by_domain(DOMAIN):
        try:
            user_location = SQLLocation.objects.get(domain=DOMAIN, location_id=user.location._id)
        except:
            pass
        if user_location:
            if user_location.location_type == 'district':
                facilities = user_location.get_children()
                fac = set()
                no_rep = 0
                if facilities:
                    for facility in facilities:
                        sp = facility.supply_point_id
                        if sp and not StockTransaction.objects.filter(
                            case_id=sp, type="stockonhand", report__date__gte=date).exists() and \
                                user.get_verified_number():
                            fac.add(str(facility.name))
                            sp_ids.add(sp)
                            no_rep += 1
                    if fac and no_rep >= len(facilities)/2:
                        send_sms_to_verified_number(user.get_verified_number(), URGENT_NON_REPORTING % user.location.name)
                        if user.email:
                            email = str(user.email)
                            send_mail('URGENT NON REPORTING', URGENT_NON_REPORTING % user_location.name,
                                      'commcarehq-noreply@dimagi.com', [email])
                        update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY,
                                        SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'region':
                districts = user_location.get_children()
                no_rep = 0
                fac = set()
                facility_count = 0
                for district in districts:
                    facilities = district.get_children()
                    if facilities:
                        for facility in facilities:
                            facility_count += 1
                            sp = facility.supply_point_id
                            if sp and not StockTransaction.objects.filter(
                                case_id=sp, type="stockonhand",
                                report__date__gte=date).exists() and user.get_verified_number():
                                fac.add(str(facility.name))
                                sp_ids.add(sp)
                                no_rep += 1
                if fac and no_rep >= facility_count/2:
                    send_sms_to_verified_number(user.get_verified_number(), URGENT_NON_REPORTING % user.location.name)
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT NON REPORTING', URGENT_NON_REPORTING % user_location.name,
                                  'commcarehq-noreply@dimagi.com', [email])
                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'country':
                regions = user_location.get_children()
                no_rep = 0
                fac = set()
                facility_count = 0
                for region in regions:
                    districts = region.get_children()
                    for district in districts:
                        facilities = district.get_children()
                        if facilities:
                            for facility in facilities:
                                facility_count += 1
                                sp = facility.supply_point_id
                                if sp and not StockTransaction.objects.filter(
                                    case_id=sp, type="stockonhand",
                                    report__date__gte=date).exists() and user.get_verified_number():
                                    fac.add(str(facility.name))
                                    sp_ids.add(sp)
                                    no_rep += 1
                if fac and no_rep >= facility_count/2:
                    send_sms_to_verified_number(user.get_verified_number(), URGENT_NON_REPORTING % user.location.name)
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT NON REPORTING', URGENT_NON_REPORTING % user_location.name,
                                  'commcarehq-noreply@dimagi.com', [email])
                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


#Urgent Stockout
@periodic_task(run_every=crontab(day_of_week=1, hour=8, minute=20),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def urgent_stockout():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=21)
    for user in CommCareUser.by_domain(DOMAIN):
        try:
            user_location = SQLLocation.objects.get(domain=DOMAIN, location_id=user.location._id)
        except:
            pass
        if user_location:
            if user_location.location_type == 'district':
                facilities = user_location.get_children()
                stocked_out_products = set()
                fac = set()
                no_rep = 0
                if facilities:
                    for facility in facilities:
                        sp = facility.supply_point_id
                        if sp:
                            stocked_out = StockTransaction.objects.filter(case_id=sp, type="stockonhand",
                                                                          stock_on_hand=0)
                            if stocked_out.exists() and user.get_verified_number():
                                no_rep += 1
                                fac.add(str(facility))
                                for product in stocked_out:
                                    stocked_out_products.add(SQLProduct.objects.get(product_id=product.product_id).name)
                                sp_ids.add(sp)
                    if fac and no_rep >= len(facilities)/2:
                        send_sms_to_verified_number(user.get_verified_number(), " ,".join(stocked_out_products))
                        if user.email:
                            email = str(user.email)
                            send_mail('URGENT STOCKOUT', URGENT_STOCKOUT % (user_location.name, ", ".join(
                                sorted([str(product) for product in stocked_out_products]))),
                                    'commcarehq-noreply@dimagi.com', [email])
                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'region':
                districts = user_location.get_children()
                no_rep = 0
                stocked_out_products = set()
                fac = set()
                facility_count = 0
                for district in districts:
                    facilities = district.get_children()
                    if facilities:
                        for facility in facilities:
                            facility_count += 1
                            sp = facility.supply_point_id
                            if sp:
                                stocked_out = StockTransaction.objects.filter(case_id=sp, type="stockonhand",
                                                                              stock_on_hand=0)
                                if stocked_out.exists() and user.get_verified_number():
                                    no_rep += 1
                                    fac.add(str(facility))
                                for product in stocked_out:
                                    stocked_out_products.add(SQLProduct.objects.get(product_id=product.product_id).name)
                                sp_ids.add(sp)
                if fac and no_rep >= facility_count/2:
                    send_sms_to_verified_number(user.get_verified_number(), " ,".join(stocked_out_products))
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT STOCKOUT', URGENT_STOCKOUT % (user_location.name,
                                                                        ", ".join(sorted([str(product) for product
                                                                                          in stocked_out_products]))),
                                  'commcarehq-noreply@dimagi.com', [email])
                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)
            elif user_location.location_type == 'country':
                regions = user_location.get_children()
                no_rep = 0
                fac = set()
                stocked_out_products = set()
                facility_count = 0
                for region in regions:
                    districts = region.get_children()
                    for district in districts:
                        facilities = district.get_children()
                        if facilities:
                            for facility in facilities:
                                facility_count += 1
                                sp = facility.supply_point_id
                                if sp:
                                    stocked_out = StockTransaction.objects.filter(case_id=sp, type="stockonhand",
                                                                                  stock_on_hand=0)
                                    if stocked_out.exists() and user.get_verified_number():
                                        no_rep += 1
                                        fac.add(str(facility))
                                    for product in stocked_out:
                                        stocked_out_products.add(SQLProduct.objects.get(product_id=product.product_id).name)
                                        sp_ids.add(sp)
                if fac and no_rep >= facility_count/2:
                    send_sms_to_verified_number(user.get_verified_number(), " ,".join(stocked_out_products))
                    if user.email:
                        email = str(user.email)
                        send_mail('URGENT STOCKOUT', URGENT_STOCKOUT % (user_location.name,
                                                                        ", ".join(sorted([str(product) for product
                                                                                          in stocked_out_products]))),
                                  'commcarehq-noreply@dimagi.com', [email])

                    update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


#Web reminder, once every 3 months
@periodic_task(run_every=crontab(day_of_month=1, hour=10, minute=3),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def reminder_to_visit_website():
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location and user.last_login < datetime.datetime.now() - datetime.timedelta(weeks=13) and\
                user.get_verified_number() \
                and (user.location.location_type == 'district' or user.location.location_type == 'region' or
                             user.location.location_type == 'country'):
                send_sms_to_verified_number(user.get_verified_number(), WEB_REMINDER % user.name)
                if user.email:
                    email = str(user.email)
                    send_mail('REMINDER TO VISIT WEBSITE', WEB_REMINDER % user.name, 'commcarehq-noreply@dimagi.com',
                              [email])


#One week reminder when facility does not report to EWS
@periodic_task(run_every=crontab(day_of_week=1, hour=11, minute=11),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def report_reminder():
    sp_ids = set()
    now = datetime.datetime.utcnow()
    date = now - datetime.timedelta(days=7)
    for user in CommCareUser.by_domain(DOMAIN):
        if user.location:
            sp = SupplyPointCase.get_by_location(user.location)
            if sp and not StockTransaction.objects.filter(
                case_id=sp._id, type="stockonhand", report__date__gte=date).exists()\
                    and user.get_verified_number():
                sp_ids.add(sp._id)
                send_sms_to_verified_number(user.get_verified_number(),
                                            REPORT_REMINDER % (user.name, user.location.name))
                if user.email:
                    email = str(user.email)
                    send_mail('REPORT REMINDER', (user.name, user.location.name), 'commcarehq-noreply@dimagi.com',
                              [email])
                update_statuses(sp_ids, SupplyPointStatusTypes.SOH_FACILITY, SupplyPointStatusValues.REMINDER_SENT)


#Checking if report was complete or not
def report_completion_check(sp_id, user):
    now = datetime.datetime.utcnow()
    reported_products = StockTransaction.objects.filter(case_id=sp_id, type='stockonhand', report_date=now)
    expected_products = SQLProduct.objects.filter(domain=DOMAIN)
    reported_products_ = set()
    expected_products_ = set()
    for product in reported_products:
        reported_products_.add(SQLProduct.objects.get(product_id=product.product_id).name)
    for product in expected_products:
        expected_products_.add(SQLProduct.objects.get(product_id=product.product_id).name)
    missing_products = set.difference(reported_products_, expected_products_)
    if len(missing_products) == 0:
        send_sms_to_verified_number(user.get_verified_number(), COMPLETE_REPORT)
        if user.email:
            email = str(user.email)
            send_mail('COMPLETE REPORT', INCOMPLETE_REPORT, 'commcarehq-noreply@dimagi.com', [email])
    elif len(missing_products) != 0:
        send_sms_to_verified_number(
            user.get_verified_number(), INCOMPLETE_REPORT % (user.name, user.location.name,
                                                             ", ".join(sorted(missing_products))))
        if user.email:
            email = str(user.email)
            send_mail('INCOMPLETE REPORT', INCOMPLETE_REPORT % (user.name, user.location.name,
                                                                ", ".join(sorted(missing_products))),
                      'commcarehq-noreply@dimagi.com', [email])


def report_below_level(sp_id, user):
    low_level = 20
    products = set()
    now = datetime.datetime.utcnow()
    reported_products_below_level = StockTransaction.objects.filter(case_id=sp_id, type='stockonhand',
                                                                    stock_on_hand__lte=low_level, report_date=now)
    if reported_products_below_level:
        for product in reported_products_below_level:
            products.add(SQLProduct.objects.get(product_id=product.product_id).name)
        send_sms_to_verified_number(
            user.get_verified_number(), BELOW_REORDER_LEVELS %
            (user.name, user.location.name,", ".join(sorted([str(product) for product in products]))))
        if user.email:
            email = str(user.email)
            send_mail('COMMODITIES BELOW RE-ORDER LEVEL',
                      BELOW_REORDER_LEVELS %
                      (user.name, user.location.name, ", ".join(sorted([str(product) for product in products]))),
                      'commcarehq-noreply@dimagi.com', [email])


def report_above_level(sp_id, user):
    now = datetime.datetime.utcnow()
    high_level = 100
    products = set()
    reported_products_above_level = StockTransaction.objects.filter(case_id=sp_id, type='stockonhand',
                                                                    stock_on_hand__gte=high_level, report_date=now)
    if reported_products_above_level:
        for product in reported_products_above_level:
            products.add(SQLProduct.objects.get(product_id=product.product_id).name)
        send_sms_to_verified_number(
            user.get_verified_number(), ABOVE_THRESHOLD % (user.name, user.location.name,
                                                           ", ".join(sorted([str(product) for product in products]))))
        if user.email:
            email = str(user.email)
            send_mail('STOCK LEVELS ABOVE MAXIMUM THRESHOLD',
                      ABOVE_THRESHOLD % (user.name, ", ".join(sorted([str(product) for product in products]))),
                      'commcarehq-noreply@dimagi.com', [email])


# reported increase in stock levels without corresponding receipts
def no_receipts(sp_id, user):
    now = datetime.datetime.utcnow()
    products = set()
    date = now - datetime.timedelta(days=7)
    current_stock_transaction = StockTransaction.objects.filter(case_id=sp_id, type='stockonhand', report__date=now)
    for product in current_stock_transaction:
        current_product_stock_state = product.stock_on_hand
        previous_product_stock_state = StockState.objects.get(case_id=sp_id, product_id=product.product_id).stock_on_hand
        if current_product_stock_state > previous_product_stock_state and not StockTransaction.objects.filter(
                case_id=sp_id, type='receipts', report__date=now).exists():
            products.add(SQLProduct.objects.get(product_id=product.product_id).name)
    if products:
        send_sms_to_verified_number(user.get_verified_number(), WITHOUT_RECEIPTS %
                                    ', '.join(sorted(str(product) for product in products)))
        if user.email:
            email = str(user.email)
            send_mail('SUBMITTED INCREASES IN STOCK LEVEL WITHOUT CORRESPONDING RECEIPTS',
                      WITHOUT_RECEIPTS % (", ".join(sorted([str(product) for product in products]))),
                      'commcarehq-noreply@dimagi.com', [email])