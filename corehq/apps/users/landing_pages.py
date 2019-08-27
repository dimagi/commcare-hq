from collections import namedtuple

from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq import toggles


class LandingPage(namedtuple('LandingPage', ['id', 'name', 'urlname'])):

    def get_urlname(self, domain):
        if callable(self.urlname):
            return self.urlname(domain)
        return self.urlname


def get_cloudcare_urlname(domain):
    from corehq.apps.cloudcare.views import FormplayerMain
    return FormplayerMain.urlname


ALL_LANDING_PAGES = (
    LandingPage('dashboard', ugettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', ugettext_noop('Web Apps'), get_cloudcare_urlname),
    LandingPage('reports', ugettext_noop('Reports'), 'reports_home'),
    # Only allowed if toggles.DATA_FILE_DOWNLOAD.enabled(domain)
    LandingPage('downloads', ugettext_noop('Data File Downloads'), 'download_data_files'),
)


def get_allowed_landing_pages(domain):
    if toggles.DATA_FILE_DOWNLOAD.enabled(domain):
        return ALL_LANDING_PAGES
    return [page for page in ALL_LANDING_PAGES if page.id != 'downloads']


def get_landing_page(id):
    for landing_page in ALL_LANDING_PAGES:
        if landing_page.id == id:
            return landing_page
    raise ValueError(_("No landing page found with id {}".format(id)))


def get_redirect_url(id, domain):
    page = get_landing_page(id)
    return reverse(page.get_urlname(domain), args=[domain])
