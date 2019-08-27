
from corehq.apps.reports.v2.exceptions import ReportNotFoundError
from corehq.apps.reports.v2.reports import explore_case_data

REPORTS = [
    explore_case_data.ExploreCaseDataReport,
]


def get_report(request, domain, slug):
    slug_to_class = dict([(c.slug, c) for c in REPORTS])
    try:
        report_class = slug_to_class[slug]
        return report_class(request, domain)
    except (KeyError, NameError):
        raise ReportNotFoundError(
            "The report config for {} cannot be found.".format(slug)
        )
