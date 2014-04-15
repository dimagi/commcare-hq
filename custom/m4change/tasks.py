from celery.schedules import crontab
from celery.task import periodic_task
from dimagi.utils.couch import sync_docs

from corehq.apps.locations.models import Location
from custom.m4change.constants import M4CHANGE_DOMAINS
from custom.m4change.fixtures import get_last_n_full_months
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource
import settings


@periodic_task(run_every=crontab(hour="3", minute="0", day_of_week="*"), queue=getattr(settings, "CELERY_PERIODIC_QUEUE", "celery"))
def generate_fixtures():

    db = FixtureReportResult.get_db()
    data_source = M4ChangeReportDataSource()
    report_slugs = data_source.get_report_slugs()

    for domain in M4CHANGE_DOMAINS:
        # Remove all FixtureReportResult instances, as they would either be deleted or replaced anyway
        db.delete_docs(FixtureReportResult.by_domain(domain=domain))

        location_ids = [location.get_id for location in Location.by_domain(domain)]
        dates = get_last_n_full_months(3)
        delete_dates = [dates[0]]
        generate_dates = [dates[1], dates[2]]

        for date in delete_dates:
            for location_id in location_ids:
                for report_slug in report_slugs:
                    start_date = date[0].strftime("%Y-%m-%d")
                    end_date = date[1].strftime("%Y-%m-%d")
                    fixture = FixtureReportResult.by_composite_key(domain, location_id, start_date, end_date, report_slug)
                    if fixture is not None:
                        fixture.delete()

        for date in generate_dates:
            for location_id in location_ids:
                data_source.configure(config={
                    "startdate": date[0],
                    "enddate": date[1],
                    "location_id": location_id,
                    "domain": domain
                })
                report_data = data_source.get_data()

                for report_slug in report_data:
                    rows = report_data[report_slug].get("data", [])
                    name = report_data[report_slug].get("name")
                    FixtureReportResult.save_result(domain, location_id, date[0].date(), date[1].date(), report_slug, rows, name)