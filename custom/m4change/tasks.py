import json
from celery.schedules import crontab
from celery.task import periodic_task

from django.conf import settings

from dimagi.utils.couch import release_lock
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.locations.models import SQLLocation
from custom.m4change.constants import NUMBER_OF_MONTHS_FOR_FIXTURES, M4CHANGE_DOMAINS, REDIS_FIXTURE_KEYS, \
    REDIS_FIXTURE_LOCK_KEYS
from custom.m4change.fixtures.report_fixtures import get_last_n_months
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource
from dimagi.utils.parsing import json_format_date


@periodic_task(run_every=crontab(hour="3", minute="0", day_of_week="*"),
               queue='background_queue')
def generate_production_fixtures():
    db = FixtureReportResult.get_db()
    data_source = M4ChangeReportDataSource()

    for domain in M4CHANGE_DOMAINS:
        generate_fixtures_for_domain(domain, db, data_source)


def generate_fixtures_for_domain(domain, db, data_source):

    location_ids = SQLLocation.active_objects.filter(domain=domain).location_ids()
    dates = get_last_n_months(NUMBER_OF_MONTHS_FOR_FIXTURES)

    for date in dates:
        for location_id in location_ids:
            data_source.configure(config={
                "startdate": date[0],
                "enddate": date[1],
                "location_id": location_id,
                "domain": domain
            })
            report_data = data_source.get_data()

            for report_slug in report_data:
                rows = dict(report_data[report_slug].get("data", []))
                name = report_data[report_slug].get("name")

                # Remove cached fixture docs
                db.delete_docs(FixtureReportResult.all_by_composite_key(domain, location_id,
                                                                        json_format_date(date[0]),
                                                                        json_format_date(date[1]), report_slug))

                FixtureReportResult.save_result(domain, location_id, date[0].date(), date[1].date(),
                                                report_slug, rows, name)


@periodic_task(run_every=crontab(hour="*", minute="*/30", day_of_week="*"),
               queue=getattr(settings, "CELERY_PERIODIC_QUEUE", "celery"))
def generate_fixtures_for_locations():

    client = get_redis_client()
    start_date, end_date = get_last_n_months(1)[0]
    db = FixtureReportResult.get_db()
    data_source = M4ChangeReportDataSource()

    for domain in M4CHANGE_DOMAINS:
        redis_key = REDIS_FIXTURE_KEYS[domain]
        redis_lock_key = REDIS_FIXTURE_LOCK_KEYS[domain]
        lock = client.lock(redis_lock_key, timeout=5)
        location_ids = []
        if lock.acquire(blocking=True):
            try:
                location_ids_str = client.get(redis_key)
                location_ids = json.loads(location_ids_str if location_ids_str else "[]")
                client.set(redis_key, '[]')
            finally:
                release_lock(lock, True)
        for location_id in location_ids:

            data_source.configure(config={
                "startdate": start_date,
                "enddate": end_date,
                "location_id": location_id,
                "domain": domain
            })
            report_data = data_source.get_data()

            for report_slug in report_data:

                # Remove cached fixture docs
                db.delete_docs(
                    FixtureReportResult.all_by_composite_key(
                        domain, location_id, json_format_date(start_date),
                        json_format_date(end_date), report_slug)
                )
                rows = dict(report_data[report_slug].get("data", []))
                name = report_data[report_slug].get("name")
                FixtureReportResult.save_result(domain, location_id, start_date.date(), end_date.date(),
                                                report_slug, rows, name)
