from collections import namedtuple

from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege

LandingPage = namedtuple('LandingPage', ['id', 'name', 'urlname'])


ALL_LANDING_PAGES = (
    LandingPage('dashboard', gettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', gettext_noop('Web Apps'), 'formplayer_main'),
    LandingPage('reports', gettext_noop('Reports'), 'reports_home'),
    # Pro plan only:
    LandingPage(
        'downloads',
        gettext_noop('Data File Downloads'),
        'download_data_files',
    ),
)


def get_allowed_landing_pages(domain):
    if domain_has_privilege(domain, privileges.DATA_FILE_DOWNLOAD):
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
