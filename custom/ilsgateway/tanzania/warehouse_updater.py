from datetime import datetime, timedelta
import logging
import itertools
from django.db.models import Q
from corehq.apps.products.models import Product
from corehq.apps.locations.models import Location, SQLLocation
from dimagi.utils.dates import get_business_day_of_month, add_months, months_between
from casexml.apps.stock.models import StockReport, StockTransaction
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, DeliveryGroups, \
    OrganizationSummary, GroupSummary, SupplyPointStatusValues, Alert, ProductAvailabilityData, \
    SupplyPointWarehouseRecord, HistoricalLocationGroup, ILSGatewayConfig


"""
    These functions and variables are ported from:
    https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/run_reports.py
"""


NEEDED_STATUS_TYPES = [SupplyPointStatusTypes.DELIVERY_FACILITY,
                       SupplyPointStatusTypes.R_AND_R_FACILITY,
                       SupplyPointStatusTypes.SUPERVISION_FACILITY,
                       SupplyPointStatusTypes.SOH_FACILITY]

NO_PRIMARY_CONTACT = 'no_primary_contact'
PRODUCT_STOCKOUT = 'product_stockout'
RR_NOT_SUBMITTED = 'rr_' + SupplyPointStatusValues.NOT_SUBMITTED
RR_NOT_RESPONDED = 'rr_not_responded'
DELIVERY_NOT_RECEIVED = 'delivery_' + SupplyPointStatusValues.NOT_RECEIVED
DELIVERY_NOT_RESPONDING = 'delivery_not_responding'
SOH_NOT_RESPONDING = 'soh_not_responding'

TEST_REGION_ID = 21

def _is_valid_status(facility, date, status_type):
    if status_type not in NEEDED_STATUS_TYPES:
        return False
    groups = HistoricalLocationGroup.objects.filter(
        date__month=date.month,
        date__year=date.year,
        location_id=facility.sql_location
    )
    if (not facility.metadata.get('group', None)) and (groups.count() == 0):
        return False

    if groups.count() > 0:
        code = groups[0].group
    else:
        code = facility.metadata['group']
    dg = DeliveryGroups(date.month)
    if status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
        return code == dg.current_submitting_group()
    elif status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
        return code == dg.current_delivering_group()
    return True


def _get_window_date(status_type, date):
    # we need this method because the soh and super reports actually
    # are sometimes treated as reports for _next_ month
    if status_type == SupplyPointStatusTypes.SOH_FACILITY or \
       status_type == SupplyPointStatusTypes.SUPERVISION_FACILITY:
        # if the date is after the last business day of the month
        # count it for the next month
        if date.date() >= get_business_day_of_month(date.year, date.month, -1):
            year, month = add_months(date.year, date.month, 1)
            return datetime(year, month, 1)
    return datetime(date.year, date.month, 1)


def is_on_time(status_date, warehouse_date, status_type):
    """
    on_time requirement
    SOH report should be submitted before 6th business day of the month.
    R & R report should be submitted before 13th business day of the month.
    Otherwise reports are marked as late response.
    """

    if status_type == SupplyPointStatusTypes.SOH_FACILITY:
        if status_date.date() < get_business_day_of_month(warehouse_date.year, warehouse_date.month, 6):
            return True
    if status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
        if status_date.date() < get_business_day_of_month(warehouse_date.year, warehouse_date.month, 13):
            return True
    return False


def average_lead_time(facility_id, window_date):
    end_date = datetime(window_date.year, window_date.month % 12 + 1, 1)
    received = SupplyPointStatus.objects.filter(
        supply_point=facility_id,
        status_date__lt=end_date,
        status_value=SupplyPointStatusValues.RECEIVED,
        status_type=SupplyPointStatusTypes.DELIVERY_FACILITY).order_by('status_date')

    total_time = timedelta(days=0)
    count = 0

    last_receipt = datetime(1900, 1, 1)
    for receipt in received:
        if receipt.status_date - last_receipt < timedelta(days=30):
            last_receipt = receipt.status_date
            continue
        last_receipt = receipt.status_date
        last_submitted = SupplyPointStatus.objects.filter(
            supply_point=facility_id,
            status_date__lt=receipt.status_date,
            status_value=SupplyPointStatusValues.SUBMITTED,
            status_type=SupplyPointStatusTypes.R_AND_R_FACILITY).order_by('-status_date')

        if last_submitted.count():
            ltime = receipt.status_date - last_submitted[0].status_date
            if timedelta(days=30) < ltime < timedelta(days=100):
                total_time += ltime
                count += 1
        else:
            continue

    return total_time / count if count else None


def needed_status_types(org_summary):
    facility = Location.get(docid=org_summary.supply_point)
    return [status_type for status_type in NEEDED_STATUS_TYPES if _is_valid_status(facility,
                                                                                   org_summary.date, status_type)]


def not_responding_facility(org_summary):
    for status_type in needed_status_types(org_summary):
        group_summary, created = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                                    title=status_type)
        group_summary.total = 1
        assert group_summary.responded in (0, 1)
        if group_summary.title == SupplyPointStatusTypes.SOH_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'soh_not_responding', {'number': 1})
        elif group_summary.title == SupplyPointStatusTypes.R_AND_R_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'rr_not_responded', {'number': 1})
        elif group_summary.title == SupplyPointStatusTypes.DELIVERY_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'delivery_not_responding', {'number': 1})
        else:
            # not an expected / needed group. ignore for now
            pass

        group_summary.save()


def update_product_availability_facility_data(org_summary):
    # product availability

    facility = Location.get(docid=org_summary.supply_point)
    assert facility.location_type == "FACILITY"
    prods = Product.ids_by_domain(facility.domain)
    for p in prods:
        product_data, created = ProductAvailabilityData.objects.get_or_create(
            product=p,
            supply_point=facility._id,
            date=org_summary.date
        )

        if created:
            # set defaults
            product_data.total = 1
            previous_reports = ProductAvailabilityData.objects.filter(
                product=p,
                supply_point=facility._id,
                date__lt=org_summary.date
            )
            if previous_reports.count():
                prev = previous_reports.order_by("-date")[0]
                product_data.with_stock = prev.with_stock
                product_data.without_stock = prev.without_stock
                product_data.without_data = prev.without_data
            else:
                # otherwise we use the defaults
                product_data.with_stock = 0
                product_data.without_stock = 0
                product_data.without_data = 1
            product_data.save()
        assert (product_data.with_stock + product_data.without_stock + product_data.without_data) == 1, \
            "bad product data config"


def populate_no_primary_alerts(location, date):
    # First of all we have to delete all existing alert for this date.
    alert = Alert.objects.filter(supply_point=location._id, date=date, type=NO_PRIMARY_CONTACT)
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
    alert = Alert.objects.filter(supply_point=facility_id, date=date, type=PRODUCT_STOCKOUT)
    alert.delete()
    # create stockout alerts
    product_data = ProductAvailabilityData.objects.filter(supply_point=facility_id, date=date, without_stock=1)
    for p in product_data:
        create_multilevel_alert(facility_id, date, PRODUCT_STOCKOUT, {'org': facility_id, 'product': p.product})


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

    if alert_type in [PRODUCT_STOCKOUT, NO_PRIMARY_CONTACT]:
        if alert_type == PRODUCT_STOCKOUT:
            text = '%s is stocked out of %s.' % (details['org'].name, details['product'].name)
        elif alert_type == NO_PRIMARY_CONTACT:
            text = '%s has no primary contact.' % details['org'].name

        alert = Alert.objects.filter(supply_point=location_id, date=date, type=alert_type, text=text)
        if not alert:
            Alert(supply_point=location_id, date=date, type=alert_type, expires=expires, text=text).save()

    else:
        if alert_type == RR_NOT_SUBMITTED:
            text = '%s have reported not submitting their R&R form as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == RR_NOT_RESPONDED:
            text = '%s did not respond to the SMS asking if they had submitted their R&R form.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == DELIVERY_NOT_RECEIVED:
            text = '%s have reported not receiving their deliveries as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == DELIVERY_NOT_RESPONDING:
            text = '%s did not respond to the SMS asking if they had received their delivery.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif alert_type == SOH_NOT_RESPONDING:
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


def default_start_date():
    return datetime(2012, 1, 1)


def _get_test_locations(domain):
    """
        returns test region and all its children
    """
    test_region = SQLLocation.objects.get(domain=domain, external_id=TEST_REGION_ID)
    sql_locations = SQLLocation.objects.filter(
        Q(domain=domain) & (Q(parent=test_region) | Q(parent__parent=test_region))
    ).order_by('id').only('location_id')
    return [sql_location.couch_location for sql_location in sql_locations] + \
           [test_region.couch_location]


def populate_report_data(start_date, end_date, domain, runner):
    # first populate all the warehouse tables for all facilities
    # hard coded to know this is the first date with data
    start_date = max(start_date, default_start_date())

    # For QA purposes generate reporting data for only some small part of data.
    if not ILSGatewayConfig.for_domain(domain).all_stock_data:
        locations = _get_test_locations(domain)
        facilities = filter(lambda location: location.location_type == 'FACILITY', locations)
        non_facilities_types = ['DISTRICT', 'REGION', 'MOHSW']
        non_facilities = []
        for location_type in non_facilities_types:
            non_facilities.extend(filter(lambda location: location.location_type == location_type, locations))
    else:
        facilities = Location.filter_by_type(domain, 'FACILITY')
        non_facilities = list(Location.filter_by_type(domain, 'DISTRICT'))
        non_facilities += list(Location.filter_by_type(domain, 'REGION'))
        non_facilities += list(Location.filter_by_type(domain, 'MOHSW'))

    if runner.location:
        if runner.location.location_type.name.upper() != 'FACILITY':
            facilities = []
            non_facilities = itertools.dropwhile(
                lambda location: location._id != runner.location.location_id,
                non_facilities
            )
        else:
            facilities = itertools.dropwhile(
                lambda location: location._id != runner.location.location_id,
                facilities
            )

    for fac in facilities:
        runner.location = fac.sql_location
        runner.save()
        process_facility_warehouse_data(fac, start_date, end_date)

    # then populate everything above a facility off a warehouse table
    for org in non_facilities:
        runner.location = org.sql_location
        runner.save()
        process_non_facility_warehouse_data(org, start_date, end_date)
    runner.location = None
    runner.save()
    # finally go back through the history and initialize empty data for any
    # newly created facilities
    update_historical_data(domain)


def process_facility_warehouse_data(facility, start_date, end_date):
    """
    process all the facility-level warehouse tables
    """
    logging.info("processing facility %s (%s)" % (facility.name, str(facility._id)))
    for alert_type in [SOH_NOT_RESPONDING, RR_NOT_RESPONDED, DELIVERY_NOT_RESPONDING]:
        alert = Alert.objects.filter(supply_point=facility._id, date__gte=start_date, date__lt=end_date,
                                     type=alert_type)
        alert.delete()

    supply_point_id = facility.linked_supply_point()._id
    location_id = facility._id
    new_statuses = SupplyPointStatus.objects.filter(
        supply_point=facility._id,
        status_date__gte=start_date,
        status_date__lt=end_date
    ).order_by('status_date')
    process_facility_statuses(location_id, new_statuses)

    new_reports = StockReport.objects.filter(
        stocktransaction__case_id=supply_point_id,
        date__gte=start_date,
        date__lt=end_date,
        stocktransaction__type='stockonhand'
    ).order_by('date')
    process_facility_product_reports(location_id, new_reports)

    new_trans = StockTransaction.objects.filter(
        case_id=supply_point_id,
        report__date__gte=start_date,
        report__date__lt=end_date
    ).order_by('report__date')
    process_facility_transactions(location_id, new_trans)

    # go through all the possible values in the date ranges
    # and make sure there are warehouse tables there
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)

        # create org_summary for every fac/date combo
        org_summary, created = OrganizationSummary.objects.get_or_create(
            supply_point=facility._id,
            date=window_date
        )

        org_summary.total_orgs = 1
        alt = average_lead_time(facility._id, window_date)
        if alt:
            alt = alt.days
        org_summary.average_lead_time_in_days = alt or 0
        org_summary.save()

        # create group_summary for every org_summary title combo
        for title in NEEDED_STATUS_TYPES:
            GroupSummary.objects.get_or_create(org_summary=org_summary,
                                               title=title)
        # update all the non-response data
        not_responding_facility(org_summary)

        # update product availability data
        update_product_availability_facility_data(org_summary)

        # alerts
        populate_no_primary_alerts(facility, window_date)
        populate_facility_stockout_alerts(facility, window_date)


def process_facility_statuses(facility_id, statuses, alerts=True):
    """
    For a given facility and list of statuses, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.
    """
    facility = Location.get(docid=facility_id)
    for status in statuses:
        warehouse_date = _get_window_date(status.status_type, status.status_date)
        if _is_valid_status(facility, status.status_date, status.status_type):
            org_summary = OrganizationSummary.objects.get_or_create(
                supply_point=facility_id,
                date=warehouse_date
            )[0]
            group_summary = GroupSummary.objects.get_or_create(
                org_summary=org_summary,
                title=status.status_type
            )[0]
            group_summary.total = 1
            if status.status_value not in (SupplyPointStatusValues.REMINDER_SENT,
                                           SupplyPointStatusValues.ALERT_SENT):
                # we've responded to this query
                group_summary.responded = 1
                if status.status_value in [SupplyPointStatusValues.SUBMITTED,
                                           SupplyPointStatusValues.RECEIVED]:
                    group_summary.complete = 1
                else:
                    group_summary.complete = group_summary.complete or 0
                if group_summary.complete:
                    if is_on_time(status.status_date, warehouse_date, status.status_type):
                        group_summary.on_time = 1
                    else:
                        group_summary.on_time = group_summary.on_time
                else:
                    group_summary.on_time = 0

                group_summary.save()

                if alerts:
                    if status.status_value == SupplyPointStatusValues.NOT_SUBMITTED \
                            and status.status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
                        create_alert(facility_id, status.status_date, RR_NOT_SUBMITTED,
                                     {'number': 1})

                    if status.status_value == SupplyPointStatusValues.NOT_RECEIVED \
                            and status.status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
                        create_alert(facility_id, status.status_date, DELIVERY_NOT_RECEIVED,
                                     {'number': 1})


def process_facility_product_reports(facility_id, reports):
    """
    For a given facility and list of ProductReports, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities. Currently this only affects stock on hand reporting
    data. We need to use this method instead of the statuses because partial
    stock on hand reports don't create valid status, but should be treated
    like valid submissions in most of the rest of the site.
    """
    months_updated = {}
    for report in reports:
        stock_transactions = report.stocktransaction_set.filter(type='stockonhand')
        assert stock_transactions.count() > 0

        warehouse_date = _get_window_date(SupplyPointStatusTypes.SOH_FACILITY, report.date)

        if warehouse_date in months_updated:
            # an optimization to avoid repeatedly doing this work for each
            # product report for the entire month
            continue

        org_summary = OrganizationSummary.objects.get_or_create(supply_point=facility_id, date=warehouse_date)[0]

        group_summary = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                           title=SupplyPointStatusTypes.SOH_FACILITY)[0]

        group_summary.total = 1
        group_summary.responded = 1
        group_summary.complete = 1
        if is_on_time(report.date, warehouse_date, SupplyPointStatusTypes.SOH_FACILITY):
            group_summary.on_time = 1
        group_summary.save()
        months_updated[warehouse_date] = None  # update the cache of stuff we've dealt with


def process_facility_transactions(facility_id, transactions):
    """
    For a given facility and list of transactions, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.

    """
    for trans in transactions:
        date = trans.report.date
        product_data = ProductAvailabilityData.objects.get_or_create(
            product=trans.product_id,
            supply_point=facility_id,
            date=datetime(date.year, date.month, 1)
        )[0]

        product_data.total = 1
        product_data.without_data = 0
        if trans.stock_on_hand <= 0:
            product_data.without_stock = 1
            product_data.with_stock = 0
        else:
            product_data.without_stock = 0
            product_data.with_stock = 1

        product_data.save()


def get_nested_children(location):
    children = []
    if not location.children:
        return [location]
    for child in location.children:
        children.extend(get_nested_children(child))
    return children


def process_non_facility_warehouse_data(location, start_date, end_date, strict=True):
    facs = get_nested_children(location)
    fac_ids = [f._id for f in facs]
    logging.info("processing non-facility %s (%s), %s children" % (location.name, str(location._id), len(facs)))
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)
        org_summary = OrganizationSummary.objects.get_or_create(supply_point=location._id, date=window_date)[0]

        org_summary.total_orgs = len(facs)
        sub_summaries = OrganizationSummary.objects.filter(date=window_date, supply_point__in=fac_ids)

        subs_with_lead_time = [s for s in sub_summaries if s.average_lead_time_in_days]
        # lead times
        if subs_with_lead_time:
            days_sum = sum([s.average_lead_time_in_days for s in subs_with_lead_time])
            org_summary.average_lead_time_in_days = days_sum / len(subs_with_lead_time)
        else:
            org_summary.average_lead_time_in_days = 0

        org_summary.save()
        # product availability
        prods = Product.ids_by_domain(location.domain)
        for p in prods:
            product_data = ProductAvailabilityData.objects.get_or_create(product=p,
                                                                         supply_point=location._id,
                                                                         date=window_date)[0]

            sub_prods = ProductAvailabilityData.objects.filter(product=p,
                                                               supply_point__in=fac_ids,
                                                               date=window_date)

            product_data.total = sum([p.total for p in sub_prods])
            if strict:
                assert product_data.total == len(facs), \
                    "total should match number of sub facilities"
            product_data.with_stock = sum([p.with_stock for p in sub_prods])
            product_data.without_stock = sum([p.without_stock for p in sub_prods])
            product_data.without_data = product_data.total - product_data.with_stock - product_data.without_stock
            product_data.save()

        dg = DeliveryGroups(month=month, facs=facs)
        for status_type in NEEDED_STATUS_TYPES:
            gsum = GroupSummary.objects.get_or_create(org_summary=org_summary, title=status_type)[0]
            sub_sums = GroupSummary.objects.filter(title=status_type, org_summary__in=sub_summaries).all()

            # TODO: see if moving the aggregation to the db makes it
            # faster, if this is slow
            gsum.total = sum([s.total for s in sub_sums])
            gsum.responded = sum([s.responded for s in sub_sums])
            gsum.on_time = sum([s.on_time for s in sub_sums])
            gsum.complete = sum([s.complete for s in sub_sums])
            # gsum.missed_response = sum([s.missed_response for s in sub_sums])
            gsum.save()

            if status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
                expected = len(dg.delivering())
            elif status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
                expected = len(dg.submitting())
            elif status_type == SupplyPointStatusTypes.SOH_FACILITY \
                    or status_type == SupplyPointStatusTypes.SUPERVISION_FACILITY:
                expected = len(facs)
            if gsum.total != expected:
                logging.info("expected %s but was %s for %s" % (expected, gsum.total, gsum))

        for alert_type in [RR_NOT_SUBMITTED, DELIVERY_NOT_RECEIVED,
                           SOH_NOT_RESPONDING, RR_NOT_RESPONDED, DELIVERY_NOT_RESPONDING]:
            sub_alerts = Alert.objects.filter(supply_point__in=fac_ids, date=window_date, type=alert_type)
            aggregate_response_alerts(location._id, window_date, sub_alerts, alert_type)


def aggregate_response_alerts(location_id, date, alerts, alert_type):
    total = sum([s.number for s in alerts])
    if total > 0:
        create_alert(location_id, date, alert_type, {'number': total})


def update_historical_data(domain):
    """
    If we don't have a record of this supply point being updated, run
    through all historical data and just fill in with zeros.
    """
    org_summaries = OrganizationSummary.objects.order_by('date')
    if org_summaries.count() == 0:
        return

    start_date = org_summaries[0].date

    if not ILSGatewayConfig.for_domain(domain).all_stock_data:
        locations = _get_test_locations(domain)
    else:
        locations = Location.by_domain(domain)

    for sp in locations:
        try:
            SupplyPointWarehouseRecord.objects.get(supply_point=sp._id)
        except SupplyPointWarehouseRecord.DoesNotExist:
            # we didn't have a record so go through and historically update
            # anything we maybe haven't touched
            opened_on = sp.linked_supply_point().opened_on
            for year, month in months_between(start_date, opened_on):
                window_date = datetime(year, month, 1)
                for cls in [OrganizationSummary, ProductAvailabilityData, GroupSummary]:
                    _init_warehouse_model(cls, sp, window_date)
            SupplyPointWarehouseRecord.objects.create(supply_point=sp._id,
                                                      create_date=datetime.utcnow())


def _init_warehouse_model(cls, location, date):
    if cls == OrganizationSummary:
        _init_default(location, date)
    elif cls == ProductAvailabilityData:
        _init_with_product(location, date)
    elif cls == GroupSummary:
        _init_group_summary(location, date)


def _init_default(location, date):
    OrganizationSummary.objects.get_or_create(supply_point=location._id, date=date)


def _init_with_product(location, date):
    for p in Product.ids_by_domain(location.domain):
        ProductAvailabilityData.objects.get_or_create(supply_point=location._id, date=date, product=p)


def _init_group_summary(location, date):
    org_summary = OrganizationSummary.objects.get(supply_point=location._id, date=date)
    for title in NEEDED_STATUS_TYPES:
        GroupSummary.objects.get_or_create(org_summary=org_summary,
                                           title=title)
