from casexml.apps.case.signals import cases_received
from custom.m4change.constants import M4CHANGE_DOMAINS, ALL_M4CHANGE_FORMS, TEST_DOMAIN
from custom.m4change.fixtures import get_last_n_months, get_last_month
from custom.m4change.models import FixtureReportResult
from custom.m4change.reports.reports import M4ChangeReportDataSource
from custom.m4change.utils import get_user_by_id


def handle_form_duplicates(sender, xform, cases, **kwargs):
    if hasattr(xform, "domain") and xform.domain in M4CHANGE_DOMAINS\
            and hasattr(xform, "xmlns") and xform.xmlns in ALL_M4CHANGE_FORMS:
        for case in cases:
            forms = case.get_forms()
            for form in forms:
                if xform.xmlns == form.xmlns and xform._id != form._id and\
                                xform.received_on.date() == form.received_on.date():
                    xform.archive()
                    return


cases_received.connect(handle_form_duplicates)


def handle_fixture_update(sender, xform, cases, **kwargs):
    if hasattr(xform, "domain") and xform.domain == TEST_DOMAIN\
            and hasattr(xform, "xmlns") and xform.xmlns in ALL_M4CHANGE_FORMS:
        db = FixtureReportResult.get_db()
        data_source = M4ChangeReportDataSource()
        date_range = get_last_month()
        location_id = get_user_by_id(xform.form['meta']['userID']).get_domain_membership(xform.domain).location_id

        results_for_last_month = FixtureReportResult.get_report_results_by_key(domain=xform.domain,
                                                                               location_id=location_id,
                                                                               start_date=date_range[0].strftime("%Y-%m-%d"),
                                                                               end_date=date_range[1].strftime("%Y-%m-%d"))
        db.delete_docs(results_for_last_month)

        data_source.configure(config={
            "startdate": date_range[0],
            "enddate": date_range[1],
            "location_id": location_id,
            "domain": xform.domain
        })
        report_data = data_source.get_data()

        for report_slug in report_data:
            rows = report_data[report_slug].get("data", [])
            name = report_data[report_slug].get("name")
            FixtureReportResult.save_result(xform.domain, location_id, date_range[0].date(), date_range[1].date(), report_slug, rows, name)

cases_received.connect(handle_fixture_update)
