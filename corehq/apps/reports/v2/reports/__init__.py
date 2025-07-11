from corehq.apps.reports.v2.exceptions import ReportNotFoundError

REPORTS = []


def get_report(request, domain, slug):
    slug_to_class = dict([(c.slug, c) for c in REPORTS])
    try:
        report_class = slug_to_class[slug]
        return report_class(request, domain)
    except (KeyError, NameError):
        raise ReportNotFoundError(
            "The report config for {} cannot be found.".format(slug)
        )
