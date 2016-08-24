import requests

from django.http import HttpResponse
from django.template.loader import render_to_string
from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.models import SQLLocation
from . import settings
from .exceptions import TableauTokenException


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
    location_type_name, location_name = _get_user_location(couch_user, domain)
    context.update({
        'view_by': location_type_name,
        'view_by_value': location_name,
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
    Takes a couch_user and returns that users level in the heirarchy and the location name
    '''
    # TODO: This needs to handle the top level where someone can see everything
    try:
        user_location_id = user.get_domain_membership(domain).location_id
        loc = SQLLocation.by_location_id(user_location_id)
        location_type_name = loc.location_type.name
        location_name = loc.name
    except Exception:
        location_type_name = 'state'
        location_name = ''
    return location_type_name, location_name


def get_tableau_trusted_url(client_ip):
    """
    Generate a login-free URL to access Tableau views for the client with IP client_ip
    See Tableau Trusted Authentication https://onlinehelp.tableau.com/current/server/en-us/trusted_auth.htm
    """
    access_token = get_tableau_access_token(settings.TABLEAU_USERNAME, client_ip)
    url = "{tableau_root}trusted/{access_token}/#/views/".format(
        tableau_root=settings.TABLEAU_ROOT,
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
        settings.TABLEU_TICKET_URL,
        data={'username': tableau_user, 'client_ip': client_ip}
    )

    if r.status_code == 200:
        if r.text == settings.TABLEAU_INVALID_TOKEN:
            raise TableauTokenException("Tableau server failed to issue a valid token")
        else:
            return r.text
    else:
        raise TableauTokenException("Token request failed with code {}".format(r.status_code))
