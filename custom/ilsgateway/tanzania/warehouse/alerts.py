from datetime import datetime
from custom.ilsgateway.tanzania.warehouse import const
from dimagi.utils.dates import add_months
from custom.ilsgateway.models import Alert, ProductAvailabilityData


def populate_no_primary_alerts(location, date):
    # First of all we have to delete all existing alert for this date.
    alert = Alert.objects.filter(supply_point=location._id, date=date, type=const.NO_PRIMARY_CONTACT)
    alert.delete()
    # create no primary contact alerts
    # TODO Too slow. Figure out better solution.
    """
    if not filter(lambda user: user.is_active and user.location and user.location._id == org._id,
                  CommCareUser.by_domain(org.domain)):
        create_multilevel_alert(org, date, NO_PRIMARY_CONTACT, {'org': org})
    """


def populate_facility_stockout_alerts(facility_id, date):
    # delete stockout alerts
    alert = Alert.objects.filter(supply_point=facility_id, date=date, type=const.PRODUCT_STOCKOUT)
    alert.delete()
    # create stockout alerts
    product_data = ProductAvailabilityData.objects.filter(supply_point=facility_id, date=date, without_stock=1)
    for p in product_data:
        create_multilevel_alert(facility_id, date, const.PRODUCT_STOCKOUT,
                                {'org': facility_id, 'product': p.product})


def create_multilevel_alert(location, date, alert_type, details):
    create_alert(location._id, date, alert_type, details)
    if location.parent is not None:
        create_multilevel_alert(location.parent, date, alert_type, details)


def create_alert(location_id, date, alert_type, details):
    text = ''
    # url = ''
    date = datetime(date.year, date.month, 1)
    expyear, expmonth = add_months(date.year, date.month, 1)
    expires = datetime(expyear, expmonth, 1)

    number = 0 if 'number' not in details else details['number']

    if alert_type in [const.PRODUCT_STOCKOUT, const.NO_PRIMARY_CONTACT]:
        if alert_type == const.PRODUCT_STOCKOUT:
            text = '%s is stocked out of %s.' % (details['org'].name, details['product'].name)
        elif alert_type == const.NO_PRIMARY_CONTACT:
            text = '%s has no primary contact.' % details['org'].name

        alert = Alert.objects.filter(supply_point=location_id, date=date, type=alert_type, text=text)
        if not alert:
            Alert(supply_point=location_id, date=date, type=alert_type, expires=expires, text=text).save()

    else:
        if alert_type == const.RR_NOT_SUBMITTED:
            text = '%s have reported not submitting their R&R form as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == const.RR_NOT_RESPONDED:
            text = '%s did not respond to the SMS asking if they had submitted their R&R form.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == const.DELIVERY_NOT_RECEIVED:
            text = '%s have reported not receiving their deliveries as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == const.DELIVERY_NOT_RESPONDING:
            text = '%s did not respond to the SMS asking if they had received their delivery.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == const.SOH_NOT_RESPONDING:
            text = '%s have not reported their stock levels for last month.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))

        alert, created = Alert.objects.get_or_create(
            supply_point=location_id,
            date=date,
            type=alert_type,
            expires=expires
        )
        alert.number = number
        alert.text = text
        alert.save()
