from collections import namedtuple
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext as _
from corehq import toggles


class LandingPage(namedtuple('LandingPage', ['id', 'name', 'urlname'])):

    def get_urlname(self, domain):
        if callable(self.urlname):
            return self.urlname(domain)
        return self.urlname


def get_cloudcare_urlname(domain):
    from corehq.apps.cloudcare.views import FormplayerMain
    if not toggles.USE_OLD_CLOUDCARE.enabled(domain):
        return FormplayerMain.urlname
    else:
        return 'corehq.apps.cloudcare.views.default'


ALLOWED_LANDING_PAGES = (
    LandingPage('dashboard', ugettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', ugettext_noop('Web Apps'), get_cloudcare_urlname),
    LandingPage('reports', ugettext_noop('Reports'), 'reports_home'),
)


def get_landing_page(id):
    for landing_page in ALLOWED_LANDING_PAGES:
        if landing_page.id == id:
            return landing_page
    raise ValueError(_("No landing page found with id {}".format(id)))


def get_redirect_url(id, domain):
    page = get_landing_page(id)
    return reverse(page.get_urlname(domain), args=[domain])
