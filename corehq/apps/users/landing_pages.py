from collections import namedtuple

from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq import toggles


LandingPage = namedtuple('LandingPage', ['id', 'name', 'urlname'])


ALL_LANDING_PAGES = (
    LandingPage('dashboard', ugettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', ugettext_noop('Web Apps'), 'formplayer_main'),
    LandingPage('reports', ugettext_noop('Reports'), 'reports_home'),
    # Only allowed if toggles.DATA_FILE_DOWNLOAD.enabled(domain)
    LandingPage('downloads', ugettext_noop('Data File Downloads'), 'download_data_files'),
)


def get_allowed_landing_pages(domain):
    if toggles.DATA_FILE_DOWNLOAD.enabled(domain):
        return ALL_LANDING_PAGES
    return [page for page in ALL_LANDING_PAGES if page.id != 'downloads']


def validate_landing_page(domain, landing_page_id):
    allowed_ids = {page.id for page in get_allowed_landing_pages(domain)}
    if landing_page_id not in allowed_ids:
        raise ValueError(_("No landing page found with ID '{}'").format(landing_page_id))

def get_landing_page(domain, landing_page_id):
    for landing_page in get_allowed_landing_pages(domain):
        if landing_page.id == landing_page_id:
            return landing_page
    raise ValueError(_("No landing page found with id {page_id}").format(page_id=landing_page_id))


def get_redirect_url(landing_page_id, domain):
    page = get_landing_page(domain, landing_page_id)
    return reverse(page.urlname, args=[domain])
