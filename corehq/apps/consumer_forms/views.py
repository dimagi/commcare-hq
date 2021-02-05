from django.http import JsonResponse

from .models import AuthenticatedLink


def access_authenticated_link(request, domain, link_id):
    try:
        link = AuthenticatedLink.objects.get(domain=domain, link_id=link_id)
        if link.is_valid():
            response_data = {
                'status': 'valid',
                'data': link.data,
            }
            return JsonResponse(response_data)
        else:
            return JsonResponse({
                'status': 'expired'
            }, status=410)
    except AuthenticatedLink.DoesNotExist:
        return JsonResponse({
            'status': 'not_authorized'
        }, status=410)
