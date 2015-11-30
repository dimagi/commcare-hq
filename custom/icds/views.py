from django.http import HttpResponse
from django.template.loader import render_to_string
import requests
from corehq import toggles


@toggles.ICDS_REPORTS.required_decorator()
def tableau(request, domain):
    context = {
        'report_view': 'POCReports/MainDashboard'
    }
    response = render_to_string('tableau.html', context)
    # trusted_ticket = _get_tableau_trusted_ticket(request.)
    return HttpResponse(response)


def _get_tableau_trusted_ticket(client_ip):
    # TODO: Add client_ip into request and configure extended checking on Tableau server
    TABLEAU_SERVER = 'https://icds.commcarehq.org/trusted'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    }
    response = requests.post(TABLEAU_SERVER, data={'username': 'tsheffels', 'client_ip': client_ip}, headers=headers)
    return response

#     Post to Tableau server
