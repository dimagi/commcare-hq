from collections import namedtuple
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext as _


LandingPage = namedtuple('LandingPage', ['id', 'name', 'urlname'])


ALLOWED_LANDING_PAGES = (
    LandingPage('dashboard', ugettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', ugettext_noop('Web Apps'), 'cloudcare_default'),
    LandingPage('reports', ugettext_noop('Reports'), 'reports_home'),
)


def get_landing_page(id):
    for landing_page in ALLOWED_LANDING_PAGES:
        if landing_page.id == id:
            return landing_page
    raise ValueError(_("No landing page found with id {}".format(id)))


def get_redirect_url(id, domain):
    page = get_landing_page(id)
    return reverse(page.urlname, args=[domain])
