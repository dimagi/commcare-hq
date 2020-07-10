from attr import attrib, attrs
from django.templatetags.static import static

from .exceptions import CustomDashboardNotFound


@attrs()
class DashboardMetadata:
    domain = attrib()
    report_id = attrib()
    template_name = attrib(default='')
    js_files = attrib(factory=list)
    css_files = attrib(factory=list)


def get_custom_dashboard_metadata(domain, report_id):
    try:
        metadata = DOMAIN_REPORT_MAP[domain][report_id]
        return DashboardMetadata(
            domain=domain,
            report_id=report_id,
            **metadata
        )
    except KeyError:
        raise CustomDashboardNotFound()


# in the future we may want figure out a way to make this configuration more pluggable
# so that the list of domains and reports isn't managed in the repository

POC_REPORTS = {
    'poc': {
        'js_files': [
            # see https://github.com/dimagi/custom-dashboard-poc
            static('custom-dashboard-poc/index-bundle.js'),
        ]
    }
}


DOMAIN_REPORT_MAP = {
    # enables the poc reports for these two domains
    'covid': POC_REPORTS,
    'dimagi': POC_REPORTS,
}
