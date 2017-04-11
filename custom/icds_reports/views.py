import requests

from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from custom.icds_reports.filters import CasteFilter, MinorityFilter, DisabledFilter, \
    ResidentFilter, MaternalStatusFilter, ChildAgeFilter, THRBeneficiaryType, ICDSMonthFilter, \
    TableauLocationFilter, ICDSYearFilter
from . import const
from .exceptions import TableauTokenException


@location_safe
@method_decorator([toggles.ICDS_REPORTS.required_decorator(), login_and_domain_required], name='dispatch')
class TableauView(TemplateView):

    template_name = 'icds_reports/tableau.html'

    filters = [
        ICDSMonthFilter,
        ICDSYearFilter,
        TableauLocationFilter,
        CasteFilter,
        MinorityFilter,
        DisabledFilter,
        ResidentFilter,
        MaternalStatusFilter,
        ChildAgeFilter,
        THRBeneficiaryType
    ]

    @property
    def domain(self):
        return self.kwargs['domain']

    @property
    def couch_user(self):
        return self.request.couch_user

    def get_context_data(self, **kwargs):
        location_type_code, user_location_id, state_id, district_id, block_id = _get_user_location(
            self.couch_user, self.domain
        )
        client_ip = self.request.META.get('X-Forwarded-For', '')
        tableau_access_url = get_tableau_trusted_url(client_ip)

        kwargs.update({
            'report_workbook': self.kwargs.get('workbook'),
            'report_worksheet': self.kwargs.get('worksheet'),
            'debug': self.request.GET.get('debug', False),
            'view_by': location_type_code,
            'view_by_value': user_location_id,
            'state_id': state_id,
            'district_id': district_id,
            'block_id': block_id,
            'tableau_access_url': tableau_access_url,
            'filters': [
                {
                    'html': view_filter(request=self.request, domain=self.domain).render(),
                    'slug': view_filter(request=self.request, domain=self.domain).slug
                }
                for view_filter in self.filters
            ]
        })
        return super(TableauView, self).get_context_data(**kwargs)


def _get_user_location(user, domain):
    '''
    Takes a couch_user and returns that users parentage and the location id
    '''
    try:
        user_location_id = user.get_domain_membership(domain).location_id
        loc = SQLLocation.by_location_id(user_location_id)
        location_type_code = loc.location_type.code

        # Assuming no web users below block level
        state_id = 'All'
        district_id = 'All'
        block_id = 'All'
        if location_type_code == 'state':
            state_id = loc.location_id
        elif location_type_code == 'district':
            state_id = loc.parent.location_id
            district_id = loc.location_id
        elif location_type_code == 'block':
            state_id = loc.parent.parent.location_id
            district_id = loc.parent.location_id
            block_id = loc.location_id

    except Exception:
        location_type_code = 'national'
        user_location_id = ''
        state_id = 'All'
        district_id = 'All'
        block_id = 'All'
    return location_type_code, user_location_id, state_id, district_id, block_id


def get_tableau_trusted_url(client_ip):
    """
    Generate a login-free URL to access Tableau views for the client with IP client_ip
    See Tableau Trusted Authentication https://onlinehelp.tableau.com/current/server/en-us/trusted_auth.htm
    """
    access_token = get_tableau_access_token(const.TABLEAU_USERNAME, client_ip)
    url = "{tableau_trusted}{access_token}/#/views/".format(
        tableau_trusted=const.TABLEAU_TICKET_URL,
        access_token=access_token
    )
    return url


def get_tableau_access_token(tableau_user, client_ip):
    """
    Request an access_token from Tableau
    Note: the IP address of the webworker that this code runs on should be configured to request tokens in Tableau

    args:
        tableau_user: username of a valid tableau_user who can access the Tableau views
        client_ip: IP address of the client who should redee be allowed to redeem the Tableau trusted token
                   if this is empty, the token returned can be redeemed on any IP address
    """
    r = requests.post(
        const.TABLEAU_TICKET_URL,
        data={'username': tableau_user, 'client_ip': client_ip},
        verify=False
    )

    if r.status_code == 200:
        if r.text == const.TABLEAU_INVALID_TOKEN:
            raise TableauTokenException("Tableau server failed to issue a valid token")
        else:
            return r.text
    else:
        raise TableauTokenException("Token request failed with code {}".format(r.status_code))
