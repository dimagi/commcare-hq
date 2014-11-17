from datetime import datetime, timedelta
import logging
from corehq.apps.products.models import Product
from corehq.apps.locations.models import Location
from dimagi.utils.dates import get_business_day_of_month, add_months, months_between
from casexml.apps.stock.models import StockReport, StockTransaction
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, DeliveryGroups, \
    OrganizationSummary, GroupSummary, SupplyPointStatusValues, Alert, ProductAvailabilityData, \
    SupplyPointWarehouseRecord, HistoricalLocationGroup


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


def _is_valid_status(facility, date, type):
    if type not in NEEDED_STATUS_TYPES:
        return False
    facility = Location.get(docid=facility)
    groups = HistoricalLocationGroup.objects.filter(
        date__month=date.month,
        date__year=date.year,
        location_id=facility.sql_location
    )
    if (not facility.metadata.get('groups', [])) and (groups.count() == 0):
        return False

    if groups.count() > 0:
        code = groups[0].group
    else:
        code = facility.metadata['groups'][0]
    dg = DeliveryGroups(date.month)
    if type == SupplyPointStatusTypes.R_AND_R_FACILITY:
        return code == dg.current_submitting_group()
    elif type == SupplyPointStatusTypes.DELIVERY_FACILITY:
        return code == dg.current_delivering_group()
    return True


def _get_window_date(type, date):
    # we need this method because the soh and super reports actually
    # are sometimes treated as reports for _next_ month
    if type == SupplyPointStatusTypes.SOH_FACILITY or \
       type == SupplyPointStatusTypes.SUPERVISION_FACILITY:
        # if the date is after the last business day of the month
        # count it for the next month
        if date.date() >= get_business_day_of_month(date.year, date.month, -1):
            year, month = add_months(date.year, date.month, 1)
            return datetime(year, month, 1)
    return datetime(date.year, date.month, 1)


def is_on_time(sp, status_date, warehouse_date, type):
    """
    on_time requirement
    SOH report should be submitted before 6th business day of the month.
    R & R report should be submitted before 13th business day of the month.
    Otherwise reports are marked as late response.
    """
    
    if type == SupplyPointStatusTypes.SOH_FACILITY:
        if status_date.date() < get_business_day_of_month(warehouse_date.year, warehouse_date.month, 6):
            return True
    if type == SupplyPointStatusTypes.R_AND_R_FACILITY:
        if status_date.date() < get_business_day_of_month(warehouse_date.year, warehouse_date.month, 13):
            return True
    return False


def average_lead_time(fac, window_date):
    end_date = datetime(window_date.year, window_date.month % 12 + 1, 1)
    received = SupplyPointStatus.objects.filter(
        supply_point=fac._id,
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
            supply_point=fac._id,
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


def not_responding_facility(org_summary):
    assert Location.get(docid=org_summary.supply_point).location_type == "FACILITY"

    def needed_status_types(org_summary):
        return [type for type in NEEDED_STATUS_TYPES if _is_valid_status(org_summary.supply_point,
                                                                         org_summary.date, type)]

    for type in needed_status_types(org_summary):
        gsum, created = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                           title=type)

        gsum.total = 1
        assert gsum.responded in (0, 1)
        if gsum.title == SupplyPointStatusTypes.SOH_FACILITY and not gsum.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'soh_not_responding', {'number': 1})
        elif gsum.title == SupplyPointStatusTypes.R_AND_R_FACILITY and not gsum.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'rr_not_responded', {'number': 1})
        elif gsum.title == SupplyPointStatusTypes.DELIVERY_FACILITY and not gsum.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.supply_point, org_summary.date,
                         'delivery_not_responding', {'number': 1})
        else:
            # not an expected / needed group. ignore for now
            pass

        gsum.save()


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


def populate_no_primary_alerts(org, date):
    # First of all we have to delete all existing alert for this date.
    alert = Alert.objects.filter(supply_point=org._id, date=date, type=NO_PRIMARY_CONTACT)
    alert.delete()
    # create no primary contact alerts
    # TODO Too slow. Figure out better solution.
    """
    if not filter(lambda user: user.is_active and user.location and user.location._id == org._id,
                  CommTrackUser.by_domain(org.domain)):
        create_multilevel_alert(org, date, NO_PRIMARY_CONTACT, {'org': org})
    """


def populate_facility_stockout_alerts(org, date):
    # delete stockout alerts
    alert = Alert.objects.filter(supply_point=org, date=date, type=PRODUCT_STOCKOUT)
    alert.delete()
    # create stockout alerts
    product_data = ProductAvailabilityData.objects.filter(supply_point=org, date=date, without_stock=1)
    for p in product_data:
        create_multilevel_alert(org, date, PRODUCT_STOCKOUT, {'org': org, 'product': p.product})


def create_multilevel_alert(org, date, type, details):
    create_alert(org._id, date, type, details)
    if org.parent is not None:
        create_multilevel_alert(org.parent, date, type, details)


def create_alert(org, date, type, details):
    text = ''
    # url = ''
    date = datetime(date.year, date.month, 1)
    expyear, expmonth = add_months(date.year, date.month, 1)
    expires = datetime(expyear, expmonth, 1)

    number = 0 if 'number' not in details else details['number']

    if type in [PRODUCT_STOCKOUT, NO_PRIMARY_CONTACT]:
        if type == PRODUCT_STOCKOUT:
            text = '%s is stocked out of %s.' % (details['org'].name, details['product'].name)
        elif type == NO_PRIMARY_CONTACT:
            text = '%s has no primary contact.' % details['org'].name

        alert = Alert.objects.filter(supply_point=org, date=date, type=type, text=text)
        if not alert:
            Alert(supply_point=org, date=date, type=type, expires=expires, text=text).save()

    else:
        if type == RR_NOT_SUBMITTED:
            text = '%s have reported not submitting their R&R form as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif type == RR_NOT_RESPONDED:
            text = '%s did not respond to the SMS asking if they had submitted their R&R form.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif type == DELIVERY_NOT_RECEIVED:
            text = '%s have reported not receiving their deliveries as of today.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif type == DELIVERY_NOT_RESPONDING:
            text = '%s did not respond to the SMS asking if they had received their delivery.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))
        elif type == SOH_NOT_RESPONDING:
            text = '%s have not reported their stock levels for last month.' % \
                   ((str(number) + ' facility') if number == 1 else (str(number) + ' facilities'))

        alert, created = Alert.objects.get_or_create(supply_point=org, date=date, type=type, expires=expires)
        alert.number = number
        alert.text = text
        alert.save()


def default_start_date():
    return datetime(2010, 11, 1)


def populate_report_data(start_date, end_date, domain=None):
    # first populate all the warehouse tables for all facilities
    # hard coded to know this is the first date with data
    start_date = max(start_date, default_start_date())
    facilities = Location.filter_by_type(domain, 'FACILITY')
    for fac in facilities:
        process_facility_warehouse_data(fac, start_date, end_date)

    # then populate everything above a facility off a warehouse table
    non_facilities = list(Location.filter_by_type(domain, 'DISTRICT'))
    non_facilities += list(Location.filter_by_type(domain, 'MOHSW'))
    non_facilities += list(Location.filter_by_type(domain, 'REGION'))
    for org in non_facilities:
        process_non_facility_warehouse_data(org, start_date, end_date)

    # finally go back through the history and initialize empty data for any
    # newly created facilities
    update_historical_data(domain)


def process_facility_warehouse_data(fac, start_date, end_date):
    """
    process all the facility-level warehouse tables
    """
    logging.info("processing facility %s (%s)" % (fac.name, str(fac._id)))
    for alert_type in [SOH_NOT_RESPONDING, RR_NOT_RESPONDED, DELIVERY_NOT_RESPONDING]:
        alert = Alert.objects.filter(supply_point=fac._id, date__gte=start_date, date__lt=end_date,
                                     type=alert_type)
        alert.delete()

    supply_point_id = fac.linked_supply_point()._id
    new_statuses = SupplyPointStatus.objects.filter(
        supply_point=fac._id,
        status_date__gte=start_date,
        status_date__lt=end_date
    ).order_by('status_date')
    process_facility_statuses(fac, new_statuses)

    new_reports = StockReport.objects.filter(
        stocktransaction__case_id=supply_point_id,
        date__gte=start_date,
        date__lt=end_date,
        stocktransaction__type='stockonhand'
    ).order_by('date')
    process_facility_product_reports(fac, new_reports)

    new_trans = StockTransaction.objects.filter(
        case_id=supply_point_id,
        report__date__gte=start_date,
        report__date__lt=end_date
    ).order_by('report__date')
    process_facility_transactions(fac, new_trans)

    # go through all the possible values in the date ranges
    # and make sure there are warehouse tables there
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)

        # create org_summary for every fac/date combo
        org_summary, created = OrganizationSummary.objects.get_or_create(supply_point=fac._id, date=window_date)

        org_summary.total_orgs = 1
        alt = average_lead_time(fac, window_date)
        if alt:
            alt = alt.days
        org_summary.average_lead_time_in_days = alt or 0
        org_summary.save()

        # create group_summary for every org_summary title combo
        for title in NEEDED_STATUS_TYPES:
            group_summary, created = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                                        title=title)
        # update all the non-response data
        not_responding_facility(org_summary)

        # update product availability data
        update_product_availability_facility_data(org_summary)

        # alerts
        populate_no_primary_alerts(fac, window_date)
        populate_facility_stockout_alerts(fac, window_date)


def process_facility_statuses(facility, statuses, alerts=True):
    """
    For a given facility and list of statuses, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.
    """
    assert facility.location_type == "FACILITY"
    for status in statuses:
        assert status.supply_point == facility._id
        warehouse_date = _get_window_date(status.status_type, status.status_date)
        if _is_valid_status(facility._id, status.status_date, status.status_type):
            org_summary = OrganizationSummary.objects.get_or_create(
                supply_point=facility._id,
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
                    if is_on_time(facility, status.status_date, warehouse_date, status.status_type):
                        group_summary.on_time = 1
                    else:
                        group_summary.on_time = group_summary.on_time
                else:
                    group_summary.on_time = 0

                group_summary.save()

                if alerts:
                    if status.status_value == SupplyPointStatusValues.NOT_SUBMITTED \
                            and status.status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
                        create_alert(facility._id, status.status_date, RR_NOT_SUBMITTED,
                                     {'number': 1})

                    if status.status_value == SupplyPointStatusValues.NOT_RECEIVED \
                            and status.status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
                        create_alert(facility._id, status.status_date, DELIVERY_NOT_RECEIVED,
                                     {'number': 1})


def process_facility_product_reports(facility, reports):
    """
    For a given facility and list of ProductReports, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities. Currently this only affects stock on hand reporting
    data. We need to use this method instead of the statuses because partial
    stock on hand reports don't create valid status, but should be treated
    like valid submissions in most of the rest of the site.
    """
    assert facility.location_type == "FACILITY"
    months_updated = {}
    for report in reports:
        stock_transaction = report.stocktransaction_set.get(type='stockonhand')
        assert stock_transaction.case_id == facility.linked_supply_point()._id
        assert stock_transaction.type
        warehouse_date = _get_window_date(SupplyPointStatusTypes.SOH_FACILITY, report.date)

        if warehouse_date in months_updated:
            # an optimization to avoid repeatedly doing this work for each
            # product report for the entire month
            continue

        org_summary = OrganizationSummary.objects.get_or_create(supply_point=facility._id, date=warehouse_date)[0]

        group_summary = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                           title=SupplyPointStatusTypes.SOH_FACILITY)[0]

        group_summary.total = 1
        group_summary.responded = 1
        group_summary.complete = 1
        if is_on_time(facility, report.date, warehouse_date, SupplyPointStatusTypes.SOH_FACILITY):
            group_summary.on_time = 1
        group_summary.save()
        months_updated[warehouse_date] = None  # update the cache of stuff we've dealt with


def process_facility_transactions(facility, transactions, default_to_previous=True):
    """
    For a given facility and list of transactions, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.

    """
    assert facility.location_type == "FACILITY"

    for trans in transactions:
        assert trans.case_id == facility.linked_supply_point()._id
        date = trans.report.date
        product_data = ProductAvailabilityData.objects.get_or_create(
            product=trans.product_id,
            supply_point=facility._id,
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


def get_nested_children(org):
    children = []
    if not org.children:
        return [org]
    for child in org.children:
        children.extend(get_nested_children(child))
    return children


def process_non_facility_warehouse_data(org, start_date, end_date, strict=True):
    facs = get_nested_children(org)
    fac_ids = [f._id for f in facs]
    logging.info("processing non-facility %s (%s), %s children" % (org.name, str(org._id), len(facs)))
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)
        org_summary = OrganizationSummary.objects.get_or_create(supply_point=org._id, date=window_date)[0]

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
        prods = Product.ids_by_domain(org.domain)
        for p in prods:
            product_data = ProductAvailabilityData.objects.get_or_create(product=p,
                                                                         supply_point=org._id,
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
        for type in NEEDED_STATUS_TYPES:
            gsum = GroupSummary.objects.get_or_create(org_summary=org_summary, title=type)[0]
            sub_sums = GroupSummary.objects.filter(title=type, org_summary__in=sub_summaries).all()

            # TODO: see if moving the aggregation to the db makes it
            # faster, if this is slow
            gsum.total = sum([s.total for s in sub_sums])
            gsum.responded = sum([s.responded for s in sub_sums])
            gsum.on_time = sum([s.on_time for s in sub_sums])
            gsum.complete = sum([s.complete for s in sub_sums])
            # gsum.missed_response = sum([s.missed_response for s in sub_sums])
            gsum.save()

            if type == SupplyPointStatusTypes.DELIVERY_FACILITY:
                expected = len(dg.delivering())
            elif type == SupplyPointStatusTypes.R_AND_R_FACILITY:
                expected = len(dg.submitting())
            elif type == SupplyPointStatusTypes.SOH_FACILITY \
                    or type == SupplyPointStatusTypes.SUPERVISION_FACILITY:
                expected = len(facs)
            if gsum.total != expected:
                logging.info("expected %s but was %s for %s" % (expected, gsum.total, gsum))

        for alert_type in [RR_NOT_SUBMITTED, DELIVERY_NOT_RECEIVED,
                           SOH_NOT_RESPONDING, RR_NOT_RESPONDED, DELIVERY_NOT_RESPONDING]:
            sub_alerts = Alert.objects.filter(supply_point__in=fac_ids, date=window_date, type=alert_type)
            aggregate_response_alerts(org, window_date, sub_alerts, alert_type)


def aggregate_response_alerts(org, date, alerts, type):
    total = sum([s.number for s in alerts])
    if total > 0:
        create_alert(org._id, date, type, {'number': total})


def update_historical_data(domain=None):
    """
    If we don't have a record of this supply point being updated, run
    through all historical data and just fill in with zeros.
    """
    org_summaries = OrganizationSummary.objects.order_by('date')
    if org_summaries.count() == 0:
        return
    start_date = org_summaries[0].date
    for sp in Location.by_domain(domain):
        try:
            SupplyPointWarehouseRecord.objects.get(supply_point=sp._id)
        except SupplyPointWarehouseRecord.DoesNotExist:
            # we didn't have a record so go through and historically update
            # anything we maybe haven't touched
            for year, month in months_between(start_date, sp.linked_supply_point().opened_on):
                window_date = datetime(year, month, 1)
                for cls in [OrganizationSummary, ProductAvailabilityData, GroupSummary]:
                    _init_warehouse_model(cls, sp, window_date)
            SupplyPointWarehouseRecord.objects.create(supply_point=sp._id,
                                                      create_date=datetime.utcnow())


def _init_warehouse_model(cls, supply_point, date):
    if cls == OrganizationSummary:
        _init_default(supply_point, date)
    elif cls == ProductAvailabilityData:
        _init_with_product(supply_point, date)
    elif cls == GroupSummary:
        _init_group_summary(supply_point, date)


def _init_default(supply_point, date):
    OrganizationSummary.objects.get_or_create(supply_point=supply_point._id, date=date)


def _init_with_product(supply_point, date):
    for p in Product.ids_by_domain(supply_point.domain):
        ProductAvailabilityData.objects.get_or_create(supply_point=supply_point._id, date=date, product=p)


def _init_group_summary(supply_point, date):
    org_summary = OrganizationSummary.objects.get(supply_point=supply_point._id, date=date)
    for title in NEEDED_STATUS_TYPES:
        GroupSummary.objects.get_or_create(org_summary=org_summary,
                                           title=title)
