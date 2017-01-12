import requests

from django.http import HttpResponse
from django.template.loader import render_to_string
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from . import const
from .exceptions import TableauTokenException


@location_safe
@toggles.ICDS_REPORTS.required_decorator()
@login_and_domain_required
def tableau(request, domain, workbook, worksheet):
    # TODO: In production we should limit this to only the actual workbook, but this makes iteration much easier
    context = {
        'report_workbook': workbook,
        'report_worksheet': worksheet,
        'debug': request.GET.get('debug', False),
    }

    # set report view-by level based on user's location level
    couch_user = getattr(request, 'couch_user', None)
    location_type_code, user_site_code, state_code, district_code, block_code = \
        _get_user_location(couch_user, domain)
    context.update({
        'view_by': location_type_code,
        'view_by_value': user_site_code,
        'state_code': state_code,
        'district_code': district_code,
        'block_code': block_code,
    })

    # the header is added by nginx
    client_ip = request.META.get('X-Forwarded-For', '')
    tableau_access_url = get_tableau_trusted_url(client_ip)

    context.update({
        'tableau_access_url': tableau_access_url,
    })

    response = render_to_string('icds_reports/tableau.html', context)
    return HttpResponse(response)


def _get_user_location(user, domain):
    '''
    Takes a couch_user and returns that users parentage and the location code
    '''
    try:
        user_location_id = user.get_domain_membership(domain).location_id
        loc = SQLLocation.by_location_id(user_location_id)
        location_type_code = loc.location_type.code

        # Assuming no web users below block level
        state_code = 'All'
        district_code = 'All'
        block_code = 'All'
        if location_type_code == 'state':
            state_code = loc.site_code
        elif location_type_code == 'district':
            state_code = loc.parent.site_code
            district_code = loc.site_code
        elif location_type_code == 'block':
            state_code = loc.parent.parent.site_code
            district_code = loc.parent.site_code
            block_code = loc.site_code

        user_site_code = loc.site_code
    except Exception:
        location_type_code = 'national'
        user_site_code = ''
        state_code = 'All'
        district_code = 'All'
        block_code = 'All'
    return location_type_code, user_site_code, state_code, district_code, block_code


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
        data={'username': tableau_user, 'client_ip': client_ip}
    )

    if r.status_code == 200:
        if r.text == const.TABLEAU_INVALID_TOKEN:
            raise TableauTokenException("Tableau server failed to issue a valid token")
        else:
            return r.text
    else:
        raise TableauTokenException("Token request failed with code {}".format(r.status_code))
