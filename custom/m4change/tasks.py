from celery.schedules import crontab
from celery.task import periodic_task

from corehq.apps.locations.models import Location
from custom.m4change.constants import NUMBER_OF_MONTHS_FOR_FIXTURES, M4CHANGE_DOMAINS
from custom.m4change.fixtures import get_last_n_months
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource
import settings


@periodic_task(run_every=crontab(hour="3", minute="0", day_of_week="*"), queue=getattr(settings, "CELERY_PERIODIC_QUEUE", "celery"))
def generate_production_fixtures():

    db = FixtureReportResult.get_db()
    data_source = M4ChangeReportDataSource()

    for domain in M4CHANGE_DOMAINS:
        generate_fixtures_for_domain(domain, db, data_source)

def generate_fixtures_for_domain(domain, db, data_source):
    # Remove all FixtureReportResult instances, as they would either be deleted or replaced anyway
    db.delete_docs(FixtureReportResult.by_domain(domain=domain))

    location_ids = [location.get_id for location in Location.by_domain(domain)]
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
                rows = report_data[report_slug].get("data", [])
                name = report_data[report_slug].get("name")
                FixtureReportResult.save_result(domain, location_id, date[0].date(), date[1].date(), report_slug, rows, name)
