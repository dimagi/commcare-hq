from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from corehq.apps.authenticated_links.models import AuthenticatedLink


def consumer_form_reference(request, domain, link_id):
    """
    Reference / proof-of-concept hard-coded implementation of consumer forms.
    """
    link = get_object_or_404(AuthenticatedLink, domain=domain, link_id=link_id)
    # print(link.get_data())
    return JsonResponse({'link': link.get_data()})


def consumer_form(request, domain, form_id):
    # todo
    pass


def consumer_form_with_link(request, domain, form_id, link_id):
    # todo
    pass
