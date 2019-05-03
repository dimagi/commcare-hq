from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
from datetime import datetime, timedelta
from functools import partial
import logging

from celery.schedules import crontab

from celery.task import task, periodic_task
from django.db import transaction
from psycopg2._psycopg import DatabaseError

from corehq.apps.locations.models import SQLLocation
from corehq.util.decorators import serial_task
from custom.ilsgateway.slab.reminders.stockout import StockoutReminder
from custom.ilsgateway.tanzania.reminders import REMINDER_MONTHLY_SOH_SUMMARY, REMINDER_MONTHLY_DELIVERY_SUMMARY
from custom.ilsgateway.tanzania.reminders.delivery import DeliveryReminder
from custom.ilsgateway.tanzania.reminders.reports import get_district_people, construct_soh_summary, \
    construct_delivery_summary
from custom.ilsgateway.tanzania.reminders.stockonhand import SOHReminder
from custom.ilsgateway.tanzania.warehouse.updater import populate_report_data, default_start_date, \
    process_facility_warehouse_data, process_non_facility_warehouse_data
from custom.ilsgateway.utils import send_for_day, send_for_all_domains, send_translated_message
from custom.ilsgateway.models import ILSGatewayConfig, ReportRun, \
    OrganizationSummary, PendingReportingDataRecalculation
from dimagi.utils.dates import get_business_day_of_month, get_business_day_of_month_before

from .oneoff import *
import six


def get_start_date(last_successful_run):
    now = datetime.utcnow()
    first_day_of_current_month = datetime(now.year, now.month, 1)
    return first_day_of_current_month if not last_successful_run else last_successful_run.end


facility_delivery_partial = partial(send_for_day, cutoff=15, reminder_class=DeliveryReminder)
district_delivery_partial = partial(send_for_day, cutoff=13, reminder_class=DeliveryReminder,
                                    location_type='DISTRICT')


@periodic_task(run_every=crontab(day_of_month="13-15", hour=11, minute=0),
               queue="logistics_reminder_queue")
def first_facility_delivery_task():
    facility_delivery_partial(15)


@periodic_task(run_every=crontab(day_of_month="20-22", hour=11, minute=0),
               queue="logistics_reminder_queue")
def second_facility_delivery_task():
    facility_delivery_partial(22)


@periodic_task(run_every=crontab(day_of_month="26-30", hour=11, minute=0),
               queue="logistics_reminder_queue")
def third_facility_delivery_task():
    facility_delivery_partial(30)


@periodic_task(run_every=crontab(day_of_month="11-13", hour=5, minute=0),
               queue="logistics_reminder_queue")
def first_district_delivery_task():
    district_delivery_partial(13)


@periodic_task(run_every=crontab(day_of_month="18-20", hour=11, minute=0),
               queue="logistics_reminder_queue")
def second_district_delivery_task():
    district_delivery_partial(20)


@periodic_task(run_every=crontab(day_of_month="26-28", hour=11, minute=0),
               queue="logistics_reminder_queue")
def third_district_delivery_task():
    district_delivery_partial(28)


def get_last_and_nth_business_day(date, n):
    last_month = datetime(date.year, date.month, 1) - timedelta(days=1)
    last_month_last_day = get_business_day_of_month(month=last_month.month, year=last_month.year, count=-1)
    nth_business_day = get_business_day_of_month(month=date.month, year=date.year, count=n)
    return last_month_last_day, nth_business_day


@periodic_task(run_every=crontab(day_of_month="26-31", hour=11, minute=0),
               queue="logistics_reminder_queue")
def first_soh_task():
    now = datetime.utcnow()
    last_business_day = get_business_day_of_month(month=now.month, year=now.year, count=-1)
    if now.day == last_business_day.day:
        send_for_all_domains(last_business_day, SOHReminder)


@periodic_task(run_every=crontab(day_of_month="1-3", hour=6, minute=0),
               queue="logistics_reminder_queue")
def second_soh_task():
    now = datetime.utcnow()
    last_month_last_day, first_business_day = get_last_and_nth_business_day(now, 1)
    if now.day == first_business_day.day:
        send_for_all_domains(last_month_last_day, SOHReminder)


@periodic_task(run_every=crontab(day_of_month="5-7", hour=5, minute=15),
               queue="logistics_reminder_queue")
def third_soh_task():
    now = datetime.utcnow()
    last_month_last_day, fifth_business_day = get_last_and_nth_business_day(now, 5)
    if now.day == fifth_business_day.day:
        send_for_all_domains(last_month_last_day, SOHReminder)


@periodic_task(run_every=crontab(day_of_month="6-8", hour=13, minute=0),
               queue="logistics_reminder_queue")
def soh_summary_task():
    """
        6th business day of the month @ 3pm Tanzania time
    """
    now = datetime.utcnow()
    sixth_business_day = get_business_day_of_month(month=now.month, year=now.year, count=6)
    if now.day != sixth_business_day.day:
        return

    for domain in ILSGatewayConfig.get_all_enabled_domains():
        for user in get_district_people(domain):
            send_translated_message(user, REMINDER_MONTHLY_SOH_SUMMARY, **construct_soh_summary(user.location))


@periodic_task(run_every=crontab(day_of_month="26-31", hour=13, minute=0),
               queue="logistics_reminder_queue")
def delivery_summary_task():
    """
        last business day of month 3pm Tanzania time
    """
    now = datetime.utcnow()
    last_business_day = get_business_day_of_month(month=now.month, year=now.year, count=-1)
    if now.day != last_business_day.day:
        return

    for domain in ILSGatewayConfig.get_all_enabled_domains():
        for user in get_district_people(domain):
            send_translated_message(
                user, REMINDER_MONTHLY_DELIVERY_SUMMARY, **construct_delivery_summary(user.location)
            )


@periodic_task(run_every=crontab(day_of_month="6-10", hour=8, minute=0),
               queue="logistics_reminder_queue")
def stockout_reminder_task():
    """
        6th business day of month
    """
    now = datetime.utcnow()
    last_business_day = get_business_day_of_month(month=now.month, year=now.year, count=6)
    if now.day != last_business_day.day:
        return

    send_for_all_domains(last_business_day, StockoutReminder)


def recalculate_on_group_change(location, last_run):
    OrganizationSummary.objects.filter(location_id=location.get_id).delete()
    process_facility_warehouse_data(location, default_start_date(), last_run.end)
    return {
        ancestor.location_type.name: {ancestor} for ancestor in location.sql_location.get_ancestors(ascending=True)
    }


def recalculate_on_parent_change(location, previous_parent_id, last_run):
    previous_parent = SQLLocation.objects.get(location_id=previous_parent_id)
    type_location_map = defaultdict(set)

    previous_ancestors = list(previous_parent.get_ancestors(include_self=True, ascending=True))
    actual_ancestors = list(location.sql_location.get_ancestors(ascending=True))

    locations_to_recalculate = set()

    i = 0
    while previous_ancestors[i] != actual_ancestors[i] and i < len(previous_ancestors):
        locations_to_recalculate.add(previous_ancestors[i])
        locations_to_recalculate.add(actual_ancestors[i])
        i += 1

    for sql_location in locations_to_recalculate:
        type_location_map[sql_location.location_type.name].add(sql_location)

    return type_location_map


@task(serializer='pickle', queue='logistics_background_queue', ignore_result=True)
def recalculation_on_location_change(domain, last_run):
    if not last_run:
        PendingReportingDataRecalculation.objects.filter(domain=domain).delete()
        return

    pending_recalculations = PendingReportingDataRecalculation.objects.filter(domain=domain).order_by('pk')
    recalcs_dict = defaultdict(list)

    for pending_recalculation in pending_recalculations:
        key = (pending_recalculation.sql_location, pending_recalculation.type)
        recalcs_dict[key].append(pending_recalculation.data)

    non_facilities_to_recalculate = defaultdict(set)
    recalculated = set()
    for (sql_location, recalculation_type), data_list in six.iteritems(recalcs_dict):
        # If there are more changes, consider earliest and latest change.
        # Thanks to this we avoid recalculations when in fact group/parent wasn't changed.
        # E.g Group is changed from A -> B and later from B -> A.
        # In this situation there is no need to recalculate data.

        if not OrganizationSummary.objects.filter(location_id=sql_location.location_id).exists():
            # There are no data for that location so there is no need to recalculate
            PendingReportingDataRecalculation.objects.filter(
                sql_location=sql_location, type=recalculation_type, domain=domain
            ).delete()
            continue

        if recalculation_type == 'group_change'\
                and data_list[0]['previous_group'] != data_list[-1]['current_group']\
                and not sql_location.location_type.administrative:
            to_recalculate = recalculate_on_group_change(sql_location, last_run)
        elif recalculation_type == 'parent_change' \
                and data_list[0]['previous_parent'] != data_list[-1]['current_parent']:
            to_recalculate = recalculate_on_parent_change(
                sql_location, data_list[0]['previous_parent'], last_run
            )
        else:
            to_recalculate = {}
        recalculated.add(sql_location)

        for location_type, sql_locations_to_recalculate in six.iteritems(to_recalculate):
            for sql_location_to_recalculate in sql_locations_to_recalculate:
                non_facilities_to_recalculate[location_type].add(sql_location_to_recalculate)

    for location_type in ["DISTRICT", "REGION", "MSDZONE", "MOHSW"]:
        for sql_location in non_facilities_to_recalculate.get(location_type, []):
            process_non_facility_warehouse_data(
                sql_location, default_start_date(), last_run.end, strict=False
            )
    PendingReportingDataRecalculation.objects.filter(
        sql_location__in=recalculated, domain=domain
    ).delete()
