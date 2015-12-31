from django.http import HttpResponse
from django.template.loader import render_to_string
import requests
from corehq import toggles
from corehq.apps.locations.models import SQLLocation


@toggles.ICDS_REPORTS.required_decorator()
def tableau(request, domain, workbook, worksheet):
    # TODO: In production we should limit this to only the actual workbook, but this makes iteration much easier
    # trusted_ticket = _get_tableau_trusted_ticket(request.)
    couch_user = request.get('couch_user', None)
    location_type_name, location_name = _get_user_permissions(couch_user, domain)

    context = {
        'report_workbook': workbook,
        'report_worksheet': worksheet,
        'view_by': location_type_name,
        'view_by_value': location_name,
        'debug': request.GET.get('debug', False),
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
