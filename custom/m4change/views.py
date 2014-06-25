from django.views.decorators.http import require_POST
from django.http.response import HttpResponse

from custom.m4change.models import McctStatus


@require_POST
def update_service_status(request, domain):
    forms = request.POST
    for lists in forms.lists():
        for list in lists:
            if list is None or len(list) < 2:
                continue
            form_id = list[0]
            new_status = list[1] if list[1].__len__() is not 1 else None
            reject_reason = list[2] if new_status == 'rejected' else None
            if new_status is not None:
                try:
                    mcct_status = McctStatus.objects.get(form_id=form_id, domain=domain)
                except McctStatus.DoesNotExist:
                    mcct_status = None
                if not mcct_status:
                    mcct_status = McctStatus(form_id=form_id, domain=domain, status=new_status)
                mcct_status.update_status(new_status, reject_reason, request.user.username)
    return HttpResponse(status=200)
