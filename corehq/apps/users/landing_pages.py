from collections import namedtuple
from django.utils.translation import ugettext_noop, ugettext as _


LandingPage = namedtuple('LandingPage', ['id', 'name', 'urlname'])


ALLOWED_LANDING_PAGES = (
    LandingPage('dashboard', ugettext_noop('Dashboard'), 'dashboard_default'),
    LandingPage('webapps', ugettext_noop('Web Apps'), 'cloudcare_default'),
    LandingPage('reports', ugettext_noop('Reports'), 'reports_home'),
)
