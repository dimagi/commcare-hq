from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import get_custom_domain_module


class ReportLookup:
    def __init__(self, report_type):
        self.report_type = report_type

    def get_reports(self, domain=None):
        attr_name = self.report_type
        from corehq import reports
        if domain:
            domain_obj = Domain.get_by_name(domain)
        else:
            domain_obj = None

        def process(reports):
            if callable(reports):
                reports = reports(domain_obj) if domain_obj else tuple()
            return tuple(reports)

        corehq_reports = process(getattr(reports, attr_name, ()))

        module_name = get_custom_domain_module(domain)
        if module_name is None:
            custom_reports = ()
        else:
            module = __import__(module_name, fromlist=['reports'])
            if hasattr(module, 'reports'):
                reports = getattr(module, 'reports')
                custom_reports = process(getattr(reports, attr_name, ()))
            else:
                custom_reports = ()

        return corehq_reports + custom_reports

    # NOTE: This is largely duplicated in ReportDispatcher.get_report
    # This should be the primary way that we resolve slugs into report objects,
    # and we should look into removing the logic from report dispatcher when possible
    def get_report(self, domain, slug):
        for name, group in self.get_reports(domain):
            for report in group:
                if report.slug == slug:
                    return report

        return None


# TODO: Relying on hard-coded paths like this makes our code brittle.
# If we do stick with this approach, this should likely be a method on each report,
# so that reports can determine their own naming conventions.
# However, a better fix would be to populate a report repository on startup that links
# report paths to report slugs, and thus allows us to store slugs, not paths, within user permissions
def get_full_report_name(report):
    if not report:
        return ''

    return report.__module__ + '.' + report.__name__
