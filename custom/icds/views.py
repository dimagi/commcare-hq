from django.http import HttpResponse
from django.template.loader import render_to_string
import requests
from corehq import toggles
from corehq.apps.locations.models import SQLLocation


@toggles.ICDS_REPORTS.required_decorator()
def tableau(request, domain, workbook, worksheet):
    # TODO: In production we should limit this to only the actual workbook, but this makes iteration much easier
    # trusted_ticket = _get_tableau_trusted_ticket(request.)
    location_type_name, location_name = _get_user_permissions(request.couch_user, domain)

    user_location_level_key = 'user_{}'.format(location_type_name)

    context = {
        'report_workbook': workbook,
        'report_worksheet': worksheet,
        'view_by': location_type_name,
        user_location_level_key: location_name,
    }

    response = render_to_string('tableau.html', context)
    return HttpResponse(response)


def _get_user_permissions(user, domain):
    '''
    Takes a couch_user and returns that users level in the heirarchy and the location name
    '''
    # TODO: This needs to handle the top level where someone can see everything
    try:
        user_location_id = user.get_domain_membership(domain).location_id
        loc = SQLLocation.by_location_id(user_location_id)
        location_type_name = loc.location_type.name
        location_name = loc.name
    except Exception as e:
        location_type_name = 'state'
        location_name = ''
    return location_type_name, location_name

def _get_tableau_trusted_ticket(client_ip):
    # TODO: Add client_ip into request and configure extended checking on Tableau server
    TABLEAU_SERVER = 'https://icds.commcarehq.org/trusted'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    }
    response = requests.post(TABLEAU_SERVER, data={'username': 'tsheffels', 'client_ip': client_ip}, headers=headers)
    return response
