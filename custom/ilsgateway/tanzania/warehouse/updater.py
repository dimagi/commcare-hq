from __future__ import absolute_import
from __future__ import division
from datetime import datetime, timedelta
import logging
import itertools
from celery.canvas import chain
from celery.task import task
from django.db import transaction, connection
from django.db.models import Q
from django.db.models.aggregates import Avg, Sum

from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.products.models import SQLProduct
from corehq.apps.locations.models import get_location, SQLLocation
from custom.ilsgateway.tanzania.warehouse import const
from custom.ilsgateway.tanzania.warehouse.alerts import populate_no_primary_alerts, \
    populate_facility_stockout_alerts, create_alert
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from dimagi.utils.dates import get_business_day_of_month, add_months, months_between
from casexml.apps.stock.models import StockReport
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, DeliveryGroups, \
    OrganizationSummary, GroupSummary, SupplyPointStatusValues, Alert, ProductAvailabilityData, \
    ILSGatewayConfig

"""
These functions and variables are ported from:
https://github.com/dimagi/logistics/blob/tz-master/logistics_project/apps/tanzania/reporting/run_reports.py
"""


def _is_valid_status(facility, date, status_type):
    if status_type not in const.NEEDED_STATUS_TYPES:
        return False

    code = facility.metadata.get('group')
    if not code:
        return False
    dg = DeliveryGroups(date.month)
    if status_type == SupplyPointStatusTypes.R_AND_R_FACILITY:
        return dg.current_submitting_group() == code
    elif status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
        return dg.current_delivering_group() == code
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
        location_id=facility_id,
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
            location_id=facility_id,
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

    return total_time // count if count else None


def needed_status_types(org_summary):
    facility = get_location(org_summary.location_id)
    return [status_type for status_type in const.NEEDED_STATUS_TYPES if _is_valid_status(facility,
                                                                                   org_summary.date, status_type)]


def not_responding_facility(org_summary):
    for status_type in needed_status_types(org_summary):
        group_summary, created = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                                    title=status_type)
        group_summary.total = 1
        assert group_summary.responded in (0, 1)
        if group_summary.title == SupplyPointStatusTypes.SOH_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.location_id, org_summary.date,
                         'soh_not_responding', {'number': 1})
        elif group_summary.title == SupplyPointStatusTypes.R_AND_R_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.location_id, org_summary.date,
                         'rr_not_responded', {'number': 1})
        elif group_summary.title == SupplyPointStatusTypes.DELIVERY_FACILITY and not group_summary.responded:
            # TODO: this might not be right unless we also clear it
            create_alert(org_summary.location_id, org_summary.date,
                         'delivery_not_responding', {'number': 1})
        else:
            # not an expected / needed group. ignore for now
            pass

        group_summary.save()


@transaction.atomic
def update_product_availability_facility_data(facility, products, start_date, end_date):
    # product availability

    existing_data = ProductAvailabilityData.objects.filter(
        date__range=(
            datetime(start_date.year, start_date.month, 1),
            datetime(end_date.year, end_date.month, 1)
        ),
        location_id=facility.get_id
    )

    product_data_dict = {
        (pa.date, pa.location_id, pa.product): pa for pa in existing_data
    }

    product_data_list = []
    previous_month = {}
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)
        for p in products:
            now = datetime.utcnow()
            if (window_date, facility.get_id, p.product_id) in product_data_dict:
                previous_month[p.product_id] = product_data_dict[window_date, facility.get_id, p.product_id]
                continue
            else:
                product_data = ProductAvailabilityData(
                    date=window_date,
                    location_id=facility.get_id,
                    product=p.product_id,
                    create_date=now,
                    update_date=now
                )

            # set defaults
            product_data.total = 1
            prev = None
            if p.product_id in previous_month:
                prev = previous_month[p.product_id]
            if not prev:
                previous_reports = ProductAvailabilityData.objects.filter(
                    product=p.product_id,
                    location_id=facility.location_id,
                    date__lt=window_date,
                    total=1
                )
                if previous_reports.count():
                    prev = previous_reports.latest('date')

            if prev:
                product_data.with_stock = prev.with_stock
                product_data.without_stock = prev.without_stock
                product_data.without_data = prev.without_data
            else:
                # otherwise we use the defaults
                product_data.with_stock = 0
                product_data.without_stock = 0
                product_data.without_data = 1
            if product_data.pk is not None:
                product_data.save()
            else:
                product_data_list.append(product_data)
            assert (product_data.with_stock + product_data.without_stock + product_data.without_data) == 1, \
                "bad product data config for %s" % product_data
            previous_month[p.product_id] = product_data
    ProductAvailabilityData.objects.bulk_create(product_data_list)


def default_start_date():
    return datetime(2012, 1, 1)


def _get_locations_by_type(domain, type_name):
    return list(SQLLocation.active_objects.filter(domain=domain, location_type__name=type_name))


def populate_report_data(start_date, end_date, domain, runner, strict=True):
    facilities = SQLLocation.objects.filter(
        location_type__name='FACILITY',
        domain=domain,
        created_at__lt=end_date
    ).order_by('pk')
    non_facilities = _get_locations_by_type(domain, 'DISTRICT')
    non_facilities += _get_locations_by_type(domain, 'REGION')
    non_facilities += _get_locations_by_type(domain, 'MSDZONE')
    non_facilities += _get_locations_by_type(domain, 'MOHSW')

    if runner.location:
        if runner.location.location_type.name.upper() != 'FACILITY':
            facilities = []
            non_facilities = itertools.dropwhile(
                lambda location: location.location_id != runner.location.location_id,
                non_facilities
            )
        else:
            facilities = itertools.dropwhile(
                lambda location: location.location_id != runner.location.location_id,
                facilities
            )

    facilities_chunked_list = chunked(facilities, 5)
    for chunk in facilities_chunked_list:
        res = chain(process_facility_warehouse_data.si(fac, start_date, end_date, runner) for fac in chunk)()
        res.get()

    non_facilities_chunked_list = chunked(non_facilities, 50)

    # then populate everything above a facility off a warehouse table
    for chunk in non_facilities_chunked_list:
        res = chain(
            process_non_facility_warehouse_data.si(org, start_date, end_date, runner, strict)
            for org in chunk
        )()
        res.get()

    runner.location = None
    runner.save()


@task(queue='logistics_background_queue')
def process_facility_warehouse_data(facility, start_date, end_date, runner=None):
    """
    process all the facility-level warehouse tables
    """
    logging.info("processing facility %s (%s)" % (facility.name, str(facility.location_id)))

    sql_location = facility.sql_location
    if runner:
        runner.location = sql_location
        runner.save()

    for alert_type in [const.SOH_NOT_RESPONDING, const.RR_NOT_RESPONDED, const.DELIVERY_NOT_RESPONDING]:
        alert = Alert.objects.filter(location_id=facility.location_id, date__gte=start_date, date__lt=end_date,
                                     type=alert_type)
        alert.delete()

    supply_point_id = sql_location.supply_point_id
    location_id = facility.location_id
    new_statuses = SupplyPointStatus.objects.filter(
        location_id=facility.location_id,
        status_date__gte=start_date,
        status_date__lt=end_date
    ).order_by('status_date')
    process_facility_statuses(location_id, new_statuses)

    new_reports = StockReport.objects.filter(
        stocktransaction__case_id=supply_point_id,
        date__gte=start_date,
        date__lt=end_date,
        stocktransaction__type='stockonhand'
    ).distinct().order_by('date')
    process_facility_product_reports(location_id, new_reports)

    new_trans = get_latest_transaction_from_each_month(supply_point_id, start_date, end_date)
    process_facility_transactions(location_id, new_trans, start_date, end_date)

    products = SQLProduct.objects.filter(domain=facility.domain, is_archived=False)
    users = get_users_by_location_id(facility.domain, facility.get_id)

    # go through all the possible values in the date ranges
    # # and make sure there are warehouse tables there
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)
        # create org_summary for every fac/date combo
        org_summary, created = OrganizationSummary.objects.get_or_create(
            location_id=facility.location_id,
            date=window_date
        )

        org_summary.total_orgs = 1
        alt = average_lead_time(facility.location_id, window_date)
        if alt:
            alt = alt.days
        org_summary.average_lead_time_in_days = alt or 0
        org_summary.save()

        # create group_summary for every org_summary title combo
        for title in const.NEEDED_STATUS_TYPES:
            GroupSummary.objects.get_or_create(org_summary=org_summary,
                                               title=title)
        # update all the non-response data
        not_responding_facility(org_summary)
        # alerts
        with transaction.atomic():
            populate_no_primary_alerts(facility, window_date, users)
            populate_facility_stockout_alerts(facility, window_date)

    update_product_availability_facility_data(facility, products, start_date, end_date)
    update_historical_data_for_location(facility)


@transaction.atomic
def process_facility_statuses(facility_id, statuses, alerts=True):
    """
    For a given facility and list of statuses, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.
    """
    facility = get_location(facility_id)
    for status in statuses:
        warehouse_date = _get_window_date(status.status_type, status.status_date)
        if _is_valid_status(facility, status.status_date, status.status_type):
            org_summary = OrganizationSummary.objects.get_or_create(
                location_id=facility_id,
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
                        create_alert(facility_id, status.status_date, const.RR_NOT_SUBMITTED,
                                     {'number': 1})

                    if status.status_value == SupplyPointStatusValues.NOT_RECEIVED \
                            and status.status_type == SupplyPointStatusTypes.DELIVERY_FACILITY:
                        create_alert(facility_id, status.status_date, const.DELIVERY_NOT_RECEIVED,
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

        org_summary = OrganizationSummary.objects.get_or_create(location_id=facility_id, date=warehouse_date)[0]

        group_summary = GroupSummary.objects.get_or_create(org_summary=org_summary,
                                                           title=SupplyPointStatusTypes.SOH_FACILITY)[0]

        group_summary.total = 1
        group_summary.responded = 1
        group_summary.complete = 1
        if is_on_time(report.date, warehouse_date, SupplyPointStatusTypes.SOH_FACILITY):
            group_summary.on_time = 1
        group_summary.save()
        months_updated[warehouse_date] = None  # update the cache of stuff we've dealt with


def get_latest_transaction_from_each_month(case_id, start_date, end_date):
    query = '''
        SELECT DISTINCT ON (year, month, st.product_id) date_part('year', sr.date) as year,
         date_part('month', sr.date) as month, st.product_id, st.stock_on_hand
        FROM stock_stocktransaction st JOIN stock_stockreport sr ON st.report_id=sr.id
         WHERE case_id=%s AND sr.date BETWEEN %s AND %s ORDER BY year DESC,
          month DESC, st.product_id, sr.date DESC;

    '''
    cursor = connection.cursor()
    cursor.execute(query, [case_id, start_date, end_date])
    return cursor.fetchall()


@transaction.atomic
def process_facility_transactions(facility_id, transactions, start_date, end_date):
    """
    For a given facility and list of transactions, update the appropriate
    data warehouse tables. This should only be called on supply points
    that are facilities.

    """
    existing_data = ProductAvailabilityData.objects.filter(
        date__range=(
            datetime(start_date.year, start_date.month, 1),
            datetime(end_date.year, end_date.month, 1)
        ),
        location_id=facility_id
    )

    product_data_dict = {
        (pa.date, pa.location_id, pa.product): pa for pa in existing_data
    }
    for year, month, product_id, stock_on_hand in transactions:
        date = datetime(int(year), int(month), 1)
        if (date, facility_id, product_id) in product_data_dict:
            product_data = product_data_dict[(date, facility_id, product_id)]
        else:
            product_data = ProductAvailabilityData(
                product=product_id,
                location_id=facility_id,
                date=date
            )
        product_data.total = 1
        product_data.without_data = 0
        if stock_on_hand <= 0:
            product_data.without_stock = 1
            product_data.with_stock = 0
        else:
            product_data.without_stock = 0
            product_data.with_stock = 1

        product_data.save()


def get_non_archived_facilities_below(location, end_date):
    return list(location.sql_location
                .get_descendants(include_self=True)
                .filter(is_archived=False,
                        location_type__name='FACILITY',
                        created_at__lt=end_date))


@task(queue='logistics_background_queue')
def process_non_facility_warehouse_data(location, start_date, end_date, runner=None, strict=True):
    facs = get_non_archived_facilities_below(location, end_date)

    start_date = datetime(start_date.year, start_date.month, 1)
    end_date = datetime(end_date.year, end_date.month, 1)

    if runner:
        runner.location = location
        runner.save()
    fac_ids = [f.location_id for f in facs]
    logging.info("processing non-facility %s (%s), %s children"
                 % (location.name, str(location.location_id), len(facs)))
    prods = SQLProduct.objects.filter(domain=location.domain, is_archived=False)

    sub_summaries = OrganizationSummary.objects.filter(
        location_id__in=fac_ids, date__range=(start_date, end_date), average_lead_time_in_days__gt=0
    ).values('date').annotate(average_time=Avg('average_lead_time_in_days'))

    sub_summaries = {
        (subsummary['date'].year, subsummary['date'].month): subsummary
        for subsummary in sub_summaries
    }

    sub_prods = ProductAvailabilityData.objects.filter(
        location_id__in=fac_ids, date__range=(start_date, end_date)
    ).values('product', 'date').annotate(
        total_sum=Sum('total'),
        with_stock_sum=Sum('with_stock'),
        without_stock_sum=Sum('without_stock'),
    )

    sub_prods = {
        ((sub_prod['date'].year, sub_prod['date'].month), sub_prod['product']): sub_prod for sub_prod in sub_prods
    }

    sub_group_summaries = GroupSummary.objects.filter(
        org_summary__location_id__in=fac_ids,
        org_summary__date__range=(start_date, end_date)
    ).values('title', 'org_summary__date').annotate(
        total_sum=Sum('total'),
        responded_sum=Sum('responded'),
        on_time_sum=Sum('on_time'),
        complete_sum=Sum('complete')
    )

    sub_group_summaries = {
        ((sub_group_summary['org_summary__date'].year, sub_group_summary['org_summary__date'].month), sub_group_summary['title']): sub_group_summary
        for sub_group_summary in sub_group_summaries
    }

    total_orgs = len(facs)
    for year, month in months_between(start_date, end_date):
        window_date = datetime(year, month, 1)
        org_summary = OrganizationSummary.objects.get_or_create(
            location_id=location.location_id, date=window_date
        )[0]

        org_summary.total_orgs = total_orgs

        # lead times
        if (year, month) in sub_summaries:
            sub_summary = sub_summaries[year, month]
            org_summary.average_lead_time_in_days = sub_summary['average_time']
        else:
            org_summary.average_lead_time_in_days = 0

        org_summary.save()
        # product availability
        for p in prods:
            product_data = ProductAvailabilityData.objects.get_or_create(product=p.product_id,
                                                                         location_id=location.location_id,
                                                                         date=window_date)[0]

            sub_prod = sub_prods.get(((year, month), p.product_id), {})

            product_data.total = sub_prod.get('total_sum', 0)
            if strict:
                assert product_data.total == total_orgs, \
                    "total should match number of sub facilities %s-%s" % (product_data.total, total_orgs)
            product_data.with_stock = sub_prod.get('with_stock_sum', 0)
            product_data.without_stock = sub_prod.get('without_stock_sum', 0)
            product_data.without_data = product_data.total - product_data.with_stock - product_data.without_stock
            product_data.save()

        dg = DeliveryGroups(month=month, facs=facs)
        for status_type in const.NEEDED_STATUS_TYPES:
            gsum = GroupSummary.objects.get_or_create(org_summary=org_summary, title=status_type)[0]

            sub_sum = sub_group_summaries.get(((year, month), status_type), {})

            gsum.total = sub_sum.get('total_sum', 0)
            gsum.responded = sub_sum.get('responded_sum', 0)
            gsum.on_time = sub_sum.get('on_time_sum', 0)
            gsum.complete = sub_sum.get('complete_sum', 0)
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

        for alert_type in [const.RR_NOT_SUBMITTED, const.DELIVERY_NOT_RECEIVED,
                           const.SOH_NOT_RESPONDING, const.RR_NOT_RESPONDED, const.DELIVERY_NOT_RESPONDING]:
            sub_alerts = Alert.objects.filter(location_id__in=fac_ids, date=window_date, type=alert_type)
            aggregate_response_alerts(location.location_id, window_date, sub_alerts, alert_type)

    update_historical_data_for_location(location)


def aggregate_response_alerts(location_id, date, alerts, alert_type):
    total = sum([s.number for s in alerts])
    if total > 0:
        create_alert(location_id, date, alert_type, {'number': total})


def update_historical_data_for_location(loc):
    """
        Fill with zeros data for all months between default start date and date of earliest location's summary.
        E.g. Location is created at 2016-02-10 and earliest summary is from 2016-03-01 whereas
        default start date is equal to 2012-01-01, so we need to generate data for all months
        between 2012-01-01 and 2016-03-01.
        This function is important for all locations created after initial run of report runner.
    """
    start_date = default_start_date()
    try:
        earliest_org_summary = OrganizationSummary.objects.filter(location_id=loc.location_id).earliest('date')
        earliest_org_summary_date = earliest_org_summary.date
    except OrganizationSummary.DoesNotExist:
        earliest_org_summary_date = loc.created_at

    if start_date >= earliest_org_summary_date:
        return

    for year, month in months_between(start_date, earliest_org_summary_date):
        window_date = datetime(year, month, 1)
        for cls in [OrganizationSummary, ProductAvailabilityData, GroupSummary]:
            _init_warehouse_model(cls, loc, window_date)


def _init_warehouse_model(cls, location, date):
    if cls == OrganizationSummary:
        _init_default(location, date)
    elif cls == ProductAvailabilityData:
        _init_with_product(location, date)
    elif cls == GroupSummary:
        _init_group_summary(location, date)


def _init_default(location, date):
    OrganizationSummary.objects.get_or_create(location_id=location.location_id, date=date)


def _init_with_product(location, date):
    for p in SQLProduct.objects.filter(domain=location.domain, is_archived=False):
        ProductAvailabilityData.objects.get_or_create(location_id=location.location_id, date=date, product=p.product_id)


def _init_group_summary(location, date):
    org_summary = OrganizationSummary.objects.get(location_id=location.location_id, date=date)
    for title in const.NEEDED_STATUS_TYPES:
        GroupSummary.objects.get_or_create(org_summary=org_summary,
                                           title=title)
